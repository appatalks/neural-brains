import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from fly_browser import validate_input


class FlyPopulationInputTests(unittest.TestCase):
    def test_population_and_inspection_are_explicit_bounded_integers(self):
        for kind,key in (("fly_count","count"),("inspect_fly","fly")):
            for count in (1,2,3):
                event={"kind":kind,key:count}
                self.assertEqual(validate_input(event),event)
            for count in (0,4,-1,True,2.,"2",None):
                with self.assertRaises(ValueError):validate_input({"kind":kind,key:count})
            with self.assertRaises(ValueError):validate_input({"kind":kind,key:2,"extra":1})


@unittest.skipUnless(importlib.util.find_spec("dm_control"),"Pinned FlyBody required for actual shared-body tests")
class SharedFlyBodyTests(unittest.TestCase):
    def scene(self):
        from fly_environment import Environment
        return Environment.load(ROOT/"experiments/fly-walking/puddle-compact-habitat.json")

    def test_three_real_bodies_have_disjoint_actuators_observations_and_equal_mass(self):
        import numpy as np
        from fly_multibody import actor_specifications,actor_observation
        from fly_unified import create_environment
        scene=self.scene()
        with create_environment(scene,1,fly_count=3,initial_position=[v*.1 for v in scene.spawn_position_mm]) as env:
            timestep=env.reset()
            specs=actor_specifications(env.task.walkers,env.physics)
            self.assertEqual([spec.shape[0] for spec,_ in specs],[65,65,65])
            self.assertEqual(len(set(int(i) for _,ids in specs for i in ids)),195)
            masses=[float(env.physics.bind(w.thorax).subtreemass) for w in env.task.walkers]
            self.assertTrue(all(abs(masses[0]-mass)<1e-12 for mass in masses))
            positions=[w.get_pose(env.physics)[0] for w in env.task.walkers]
            self.assertEqual(len(set(round(float(position[1]),8) for position in positions)),3)
            for w in env.task.walkers:
                obs=actor_observation(timestep.observation,w)
                self.assertIn("walker/joints_pos",obs)
                self.assertTrue(all(key.startswith("walker/") for key in obs))
            action=np.zeros(env.action_spec().shape)
            action[65]=min(.1,float(specs[1][0].maximum[0]))
            env.step(action)
            np.testing.assert_array_equal(env.physics.data.ctrl[specs[0][1]],0.)
            np.testing.assert_array_equal(env.physics.data.ctrl[specs[1][1]],action[65:130])
            np.testing.assert_array_equal(env.physics.data.ctrl[specs[2][1]],0.)

    def test_initially_separated_bodies_can_make_actual_shared_world_contact(self):
        import numpy as np
        import mujoco as mj
        from fly_unified import create_environment
        with create_environment(self.scene(),1,fly_count=2) as env:
            env.reset()
            model,data=env.physics.model.ptr,env.physics.data.ptr
            first,second=env.task.walkers
            position,quat=first.get_pose(env.physics)
            second.set_pose(env.physics,position,quat)
            mj.mj_forward(model,data)
            a={model.geom(i).id for i in range(model.ngeom) if (model.geom(i).name or "").startswith(first.name+"/")}
            b={model.geom(i).id for i in range(model.ngeom) if (model.geom(i).name or "").startswith(second.name+"/")}
            self.assertTrue(any((c.geom1 in a and c.geom2 in b) or (c.geom2 in a and c.geom1 in b)
                                for c in data.contact[:data.ncon]))

    def test_invalid_population_fails_before_model_creation(self):
        from fly_unified import create_environment
        for count in (0,4,True,1.5):
            with self.assertRaises(ValueError):create_environment(self.scene(),1,fly_count=count)
