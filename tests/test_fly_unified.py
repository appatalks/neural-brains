import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_unified import evaluate_motor, named_indices
from fly_environment import Environment
from fly_objects import Objects, set_flight_object_position


class UnifiedMotorTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("dm_control"), "Pinned FlyBody environment required")
    def test_placed_objects_collide_away_from_original_static_bounds(self):
        import mujoco as mj
        import numpy as np
        from fly_unified import create_environment

        root = Path(__file__).resolve().parents[1]
        scene = Environment.load(root/"experiments/fly-walking/grassland-habitat.json")
        with create_environment(scene, 1, interactive=True, initial_position=[6.25, 0, .1278]) as env:
            env.reset()
            model, data = env.physics.model.ptr, env.physics.data.ptr
            fly_geoms = {i for i in range(model.ngeom) if model.geom(i).name.startswith("walker/")}
            objects = Objects(scene.half_size_mm)
            for kind in ("box", "sphere"):
                item = objects.place(kind, [62.5, 0, 0])
                geom = model.geom(item["name"]).id
                before_qpos, before_qvel = data.qpos.copy(), data.qvel.copy()
                set_flight_object_position(model, data, item["name"], item["position_mm"])
                mj.mj_forward(model, data)
                np.testing.assert_array_equal(data.qpos, before_qpos)
                np.testing.assert_array_equal(data.qvel, before_qvel)
                np.testing.assert_allclose(data.geom_xpos[geom], np.array(item["position_mm"])*.1)
                contacts = [c for c in data.contact[:data.ncon]
                            if (c.geom1 == geom and c.geom2 in fly_geoms)
                            or (c.geom2 == geom and c.geom1 in fly_geoms)]
                self.assertTrue(contacts, kind)
                self.assertTrue(any(c.dist < 0 for c in contacts), kind)
                constrained = [c for c in contacts if c.efc_address >= 0]
                self.assertTrue(constrained, kind)
                self.assertTrue(any(data.efc_force[c.efc_address] > 0 for c in constrained), kind)
                hit = np.zeros(1, dtype=np.int32)
                distance = mj.mj_ray(model, data, np.array([6.25, 0, 1.]),
                                     np.array([0., 0., -1.]), None, True,
                                     model.body("walker/thorax").id, hit)
                self.assertEqual(hit[0], geom)
                self.assertGreater(distance, 0)
                from fly_graphics import ObserverScene
                observer = ObserverScene(model, data)
                np.testing.assert_array_equal(observer.data.geom_xpos[geom], data.geom_xpos[geom])
                np.testing.assert_array_equal(data.qpos, before_qpos)
                np.testing.assert_array_equal(data.qvel, before_qvel)
                set_flight_object_position(model, data, item["name"], [80, 20, .8])
                mj.mj_forward(model, data)
                self.assertFalse(any(geom in (c.geom1, c.geom2) for c in data.contact[:data.ncon]))
                set_flight_object_position(model, data, item["name"])
                mj.mj_forward(model, data)
                np.testing.assert_array_equal(data.geom_xpos[geom], [0, 0, -10])
                self.assertFalse(any(geom in (c.geom1, c.geom2) for c in data.contact[:data.ncon]))
                env.reset()
                set_flight_object_position(model, data, item["name"], item["position_mm"])
                mj.mj_forward(model, data)
                self.assertTrue(any(geom in (c.geom1, c.geom2) for c in data.contact[:data.ncon]))
                set_flight_object_position(model, data, item["name"])

    def test_channels_are_mapped_by_name_not_offset(self):
        self.assertEqual(named_indices(["leg", "wing", "head"], ["head", "leg"]), [2, 0])
        for available, required in [(["leg"], ["wing"]), (["leg", "leg"], ["leg"]),
                                    (["leg"], ["leg", "leg"])]:
            with self.assertRaises(ValueError):
                named_indices(available, required)

    def evaluate(self, **changes):
        values = dict(
            records=[{"position_error_cm": 0.04}], initial=[0, 0, 0.1278],
            final=[2, 0, 0.1278], upright=0.99, seconds=1, speed=2,
            airborne=False, takeoff=False, landing=False, trigger_time=None,
            initial_contact=True, flight_steps=0, flight_contacts=0, boundary_steps=0,
            landed_at=None, model_unchanged=True,
        )
        values.update(changes)
        return evaluate_motor(**values)

    def test_walking_thresholds_and_boundary_failures(self):
        self.assertTrue(self.evaluate()[0])
        for changes in [{"upright": 0.8}, {"final": [0.99, 0, 0.1278]},
                        {"records": [{"position_error_cm": 0.151}]},
                        {"boundary_steps": 1}, {"model_unchanged": False}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.evaluate(**changes)[0])

    def test_flight_requires_no_floor_contact(self):
        args = dict(airborne=True, speed=20, final=[20, 0, 1], upright=0.7)
        passed, thresholds = self.evaluate(**args)
        self.assertTrue(passed)
        self.assertEqual(thresholds["minimum_upright_cosine"], 0.4)
        self.assertFalse(self.evaluate(**args, flight_contacts=1)[0])

    def test_takeoff_requires_trigger_sustained_flight_and_arena(self):
        args = dict(takeoff=True, trigger_time=0.32, flight_steps=2500, final=[20, 0, 1])
        self.assertTrue(self.evaluate(**args)[0])
        for changes in [{"trigger_time": None}, {"flight_steps": 2499},
                        {"initial_contact": False}, {"boundary_steps": 1},
                        {"flight_contacts": 1}, {"final": [20, 0, 0.5]}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.evaluate(**{**args, **changes})[0])

    def test_landing_does_not_require_airborne_final_height(self):
        args = dict(takeoff=True, landing=True, trigger_time=0.32, flight_steps=3000,
                    seconds=3, landed_at=2.5, final=[20, 0, 0.1278])
        passed, thresholds = self.evaluate(**args)
        self.assertTrue(passed)
        self.assertNotIn("minimum_final_height_cm", thresholds)
        self.assertFalse(self.evaluate(**{**args, "landed_at": None})[0])
        self.assertFalse(self.evaluate(**{**args, "landed_at": 2.8})[0])
        self.assertFalse(self.evaluate(**{**args, "upright": 0.7})[0])


if __name__ == "__main__":
    unittest.main()
