import copy
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from fly_environment import Environment,environment_dict
from fly_feeding import FeedingConfig
from fly_flight_arena import geometry_definitions
from fly_water import FluidPhysics

SCENE=ROOT/"experiments/fly-walking/puddle-habitat.json"


class PuddleTests(unittest.TestCase):
    def test_versioned_scene_and_food_match(self):
        scene=Environment.load(SCENE)
        self.assertEqual(scene.schema_version,4)
        self.assertEqual(len(scene.objects),78)
        self.assertEqual(len(scene.movable_objects),4)
        self.assertEqual(scene.water_regions[0].position_mm[:2],(0.,0.))
        self.assertEqual(json.loads(json.dumps(environment_dict(scene))),json.loads(SCENE.read_text()))
        food=FeedingConfig.load(ROOT/"experiments/flywire-sugar/puddle-feeding.json")
        self.assertEqual(len(food.regions),4)
        self.assertFalse(food.exposure([.6,0,.9278])["sugar_contact"])
        for _,position,_ in food.regions:
            self.assertTrue(food.exposure(position)["sugar_contact"])
            self.assertFalse(food.exposure(position,False)["sugar_contact"])
        objects={obj.name:obj for obj in scene.objects}
        self.assertEqual(objects["fruit_food_surface"].position_mm[:2],food.regions[1][1][:2])
        self.assertEqual(objects["island_sugar_a"].position_mm[:2],food.regions[0][1][:2])

    def test_water_validation_and_legacy_serialization(self):
        raw=json.loads(SCENE.read_text())
        for key,value in (("depth_mm",-1),("depth_mm",1),("radius_mm",200),
                          ("density_mg_mm3",True),("drag_rate_s",math.nan),("material","unknown")):
            changed=copy.deepcopy(raw);changed["water_regions"][0][key]=value
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/"bad.json";path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):Environment.load(path)
        old=Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json")
        self.assertFalse(old.water_regions)
        self.assertNotIn("water_regions",environment_dict(old))
        self.assertEqual(old.schema_version,3)

    def test_rigid_and_fluid_surface_geometry_are_distinct(self):
        scene=Environment.load(SCENE)
        for enabled,collision in ((False,1),(True,0)):
            water=next(row for row in geometry_definitions(scene,enabled) if row["name"]=="central_puddle")
            self.assertEqual(water["contype"],collision)
            self.assertEqual(water["conaffinity"],collision)
            self.assertAlmostEqual(water["pos"][2]+water["size"][1],.015)
            self.assertAlmostEqual(water["size"][0],1.4)


@unittest.skipUnless(importlib.util.find_spec("mujoco"),"MuJoCo required for actual fluid mechanics")
class FluidTests(unittest.TestCase):
    def setUp(self):
        import mujoco as mj
        self.mj=mj
        self.scene=Environment.load(SCENE)
        self.model=mj.MjModel.from_xml_string("""<mujoco>
          <option timestep=".0002" gravity="0 0 -981"/>
          <worldbody><geom type="plane" size="5 5 .1"/>
            <body name="floating_leaf_body" pos="0 0 .03"><freejoint/>
              <geom name="floating_leaf" type="box" size=".25 .12 .006" mass=".00002"/>
            </body></worldbody></mujoco>""")
        self.data=mj.MjData(self.model)
        self.physics=FluidPhysics(self.model,self.scene)

    def test_dry_zero_forces_and_wet_drag_do_not_modify_pose(self):
        import numpy as np
        self.mj.mj_forward(self.model,self.data)
        self.physics.apply(self.data)
        np.testing.assert_array_equal(self.data.xfrc_applied,0.)
        self.data.qpos[2]=.01;self.data.qvel[0]=2.
        self.mj.mj_forward(self.model,self.data)
        pose,velocity=self.data.qpos.copy(),self.data.qvel.copy()
        self.data.xfrc_applied.fill(0);self.physics.apply(self.data)
        body=self.model.body("floating_leaf_body").id
        self.assertGreater(self.physics.force[body,2],0)
        self.assertLess(self.physics.force[body,0],0)
        self.assertLessEqual(np.linalg.norm(self.physics.force[body,:3]),4*self.model.body_mass[body]*981+1e-12)
        np.testing.assert_array_equal(self.data.qpos,pose)
        np.testing.assert_array_equal(self.data.qvel,velocity)
        json.dumps(self.physics.snapshot(),allow_nan=False)

    def test_actual_floating_equilibrium_and_exact_replay(self):
        import numpy as np
        traces=[]
        for _ in range(2):
            self.mj.mj_resetData(self.model,self.data)
            trace=[]
            for step in range(5000):
                self.mj.mj_forward(self.model,self.data)
                self.data.xfrc_applied.fill(0)
                self.physics.apply(self.data)
                self.mj.mj_step(self.model,self.data)
                if step%10==0:trace.append(self.data.qpos.copy())
            traces.append(np.array(trace))
        expected=.015+.006-self.model.body_mass[self.model.body("floating_leaf_body").id]/(.5*.24)
        self.assertAlmostEqual(self.data.qpos[2],expected,delta=.0005)
        self.assertLess(abs(self.data.qvel[2]),.01)
        np.testing.assert_array_equal(traces[0],traces[1])

    def test_force_hold_covers_actual_four_physics_substeps(self):
        self.model.opt.timestep=.00005
        physics=FluidPhysics(self.model,self.scene,force_dt=.0002)
        for _ in range(5000):
            self.mj.mj_forward(self.model,self.data)
            self.data.xfrc_applied.fill(0)
            physics.apply(self.data)
            for _ in range(4):self.mj.mj_step(self.model,self.data)
        expected=.015+.006-.00002/(.5*.24)
        self.assertAlmostEqual(self.data.qpos[2],expected,delta=.0005)
        self.assertLess(abs(self.data.qvel[2]),.01)

    @unittest.skipUnless(importlib.util.find_spec("dm_control"),"FlyBody required for habitat contact validation")
    def test_compiled_fly_water_coverage_and_leaf_support(self):
        from fly_unified import create_environment
        from fly_flight_arena import FlyContactReader
        for enabled in (False,True):
            with create_environment(self.scene,1,fluid_physics=enabled) as env:
                env.reset()
                model,data=env.physics.model.ptr,env.physics.data.ptr
                if enabled:
                    fluid=FluidPhysics(model,self.scene)
                    fluid.apply(data)
                    self.assertTrue(fluid.geoms)
                reader=FlyContactReader(model,self.scene)
                self.assertIn(model.geom("leaf_island").id,reader.support)
                self.assertEqual(model.geom_contype[model.geom("central_puddle").id],0 if enabled else 1)
