import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fly_environment import Environment, environment_dict, object_definitions
from fly_feeding import FeedingConfig
from fly_flight_arena import geometry_definitions, make_arena


class PlantedHabitatTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "experiments/fly-walking/planted-habitat.json"
        self.raw = json.loads(self.path.read_text())
        self.environment = Environment.load(self.path)

    def load_changed(self, raw):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scene.json"
            path.write_text(json.dumps(raw))
            return Environment.load(path)

    def test_versioned_scene_roundtrip_and_old_schema_preserved(self):
        self.assertEqual(self.load_changed(environment_dict(self.environment)), self.environment)
        old = Environment.load(ROOT / "experiments/fly-walking/habitat.json")
        self.assertNotIn("objects", environment_dict(old))
        self.assertNotIn("materials", environment_dict(old))
        self.assertEqual(len(self.environment.objects), 13)
        self.assertEqual(len(self.environment.materials), 7)

    def test_unknown_materials_shapes_and_invalid_geometry_rejected(self):
        for field, value in [
            ("material", "missing"), ("kind", "mesh"), ("size_mm", [0, 1, 1]),
            ("position_mm", [29.9, 7, 4]), ("position_mm", [-10, 7, 0]),
            ("name", "groundplane"), ("name", "arena_wall_0"),
        ]:
            with self.subTest(field=field):
                raw = copy.deepcopy(self.raw)
                raw["objects"][0][field] = value
                with self.assertRaises(ValueError):
                    self.load_changed(raw)

    def test_invalid_materials_and_duplicate_names_rejected(self):
        for field, value in [("rgba", [1.1, 0, 0, 1]), ("friction", [-1, 0, 0]),
                             ("specular", 1.1), ("shininess", True)]:
            with self.subTest(field=field):
                raw = copy.deepcopy(self.raw)
                raw["materials"][0][field] = value
                with self.assertRaises(ValueError):
                    self.load_changed(raw)
        raw = copy.deepcopy(self.raw)
        raw["objects"][1]["name"] = raw["objects"][0]["name"]
        with self.assertRaises(ValueError):
            self.load_changed(raw)

    def test_shapes_materials_and_contact_units_match_backends(self):
        walking = object_definitions(self.environment)
        flight = {item["name"]: item for item in geometry_definitions(self.environment)}
        for item in walking:
            other = flight[item["name"]]
            self.assertEqual(item["type"], other["type"])
            self.assertEqual(item["friction"], other["friction"])
            self.assertEqual(item["material"], other["material"])
            for key in ["pos", "size"]:
                for a, b in zip(item[key], other[key]):
                    self.assertAlmostEqual(a, 10*b)
            self.assertEqual(item["quat"], other["quat"])

    def test_food_exposure_and_odor_are_explicitly_aligned(self):
        food = FeedingConfig.load(ROOT / "experiments/flywire-sugar/planted-feeding.json")
        self.assertTrue(food.exposure([9, 2, 1])["sugar_contact"])
        self.assertFalse(food.exposure([0.6, 0, 0.45])["sugar_contact"])
        self.assertFalse(food.exposure([9, 2, 1], enabled=False)["sugar_contact"])
        odor = next(s for s in self.environment.odors if s.name == "fruit_odor_proxy")
        self.assertEqual(odor.position_mm, food.position_mm)
        self.assertGreater(odor.value_at(food.position_mm), odor.value_at([0, 0, 0]))

    @unittest.skipUnless(importlib.util.find_spec("dm_control"), "Flight environment required")
    def test_compiled_flight_objects_have_real_contact_and_materials(self):
        import mujoco as mj
        import numpy as np
        from dm_control import mjcf
        arena = make_arena(self.environment)
        physics = mjcf.Physics.from_mjcf_model(arena.mjcf_model)
        try:
            for obj in self.environment.objects:
                index = physics.model.name2id(obj.name, "geom")
                self.assertGreater(physics.model.geom_contype[index], 0)
                self.assertGreater(physics.model.geom_conaffinity[index], 0)
                self.assertGreaterEqual(physics.model.geom_matid[index], 0)
                self.assertEqual(physics.model.geom_group[index], 0)
            mj.mj_forward(physics.model.ptr, physics.data.ptr)
            hit = np.zeros(1, dtype=np.int32)
            distance = mj.mj_ray(
                physics.model.ptr, physics.data.ptr, np.array([-1.25, 0.7, 0.65]),
                np.array([0., 0, -1]), np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8),
                True, -1, hit,
            )
            self.assertGreater(distance, 0)
            self.assertEqual(hit[0], physics.model.name2id("plant_a_leaf_left", "geom"))
        finally:
            physics.free()

    @unittest.skipUnless(importlib.util.find_spec("flygym"), "Walking environment required")
    def test_compiled_walking_plants_are_contact_and_visibility_geometry(self):
        import mujoco as mj
        import numpy as np
        from fly_walking import build_scene
        sim, *_ = build_scene(self.environment)
        try:
            for obj in self.environment.objects:
                index = sim.mj_model.geom(obj.name).id
                self.assertGreaterEqual(sim.mj_model.geom_matid[index], 0)
                self.assertEqual(sim.mj_model.geom_group[index], 0)
                # FlyGym uses explicit ground-contact pairs, not collision masks.
                pairs = zip(sim.mj_model.pair_geom1, sim.mj_model.pair_geom2)
                self.assertTrue(any(index in pair for pair in pairs), obj.name)
            hit = np.zeros(1, dtype=np.int32)
            distance = mj.mj_ray(
                sim.mj_model, sim.mj_data, np.array([-12.5, 7, 6.5]), np.array([0., 0, -1]),
                np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, -1, hit,
            )
            self.assertGreater(distance, 0)
            self.assertEqual(hit[0], sim.mj_model.geom("plant_a_leaf_left").id)
        finally:
            if sim.eye_renderer is not None:
                sim.eye_renderer.close()


if __name__ == "__main__":
    unittest.main()
