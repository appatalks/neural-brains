import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fly_environment import Environment
from fly_flight_arena import geometry_definitions, make_arena


class SharedFlightArenaTests(unittest.TestCase):
    def setUp(self):
        self.habitat = Environment.load(ROOT / "experiments/fly-walking/habitat.json")

    def test_terrain_positions_sizes_and_collisions_converted(self):
        definitions = geometry_definitions(self.habitat)
        bar = next(item for item in definitions if item["name"] == "low_bar")
        self.assertEqual(bar["pos"], [0.5, 0, 0.015])
        self.assertEqual(bar["size"], [0.02, 0.3, 0.015])
        self.assertEqual(bar["contype"], 1)
        self.assertEqual(bar["friction"], [1, 0.005, 0.0001])

    def test_walls_match_original_bounds(self):
        walls = [item for item in geometry_definitions(self.habitat) if item["name"].startswith("arena_wall")]
        self.assertEqual(len(walls), 4)
        self.assertEqual(walls[0]["pos"], [3, 0, 0.15])
        self.assertEqual(walls[0]["size"], [0.025, 3, 0.15])

    def test_source_markers_are_nonphysical(self):
        definitions = geometry_definitions(self.habitat)
        for name in ["odor_patch", "light_patch"]:
            source = next(item for item in definitions if item["name"] == name)
            self.assertEqual(source["contype"], 0)
            self.assertEqual(source["conaffinity"], 0)
            self.assertEqual(source["group"], 2)

    def test_reserved_name_collision_is_rejected(self):
        bar = replace(self.habitat.terrain[0], name="arena_wall_0")
        with self.assertRaises(ValueError):
            geometry_definitions(replace(self.habitat, terrain=(bar,)))

    @unittest.skipUnless(importlib.util.find_spec("dm_control"), "Requires flight environment")
    def test_compiled_environment_geometry(self):
        import mujoco as mj
        import numpy as np

        arena = make_arena(self.habitat)
        model = mj.MjModel.from_xml_string(
            arena.mjcf_model.to_xml_string(), assets=arena.mjcf_model.get_assets()
        )
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        bar = mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, "low_bar")
        np.testing.assert_allclose(model.geom_pos[bar], [0.5, 0, 0.015])
        hit = np.zeros(1, dtype=np.int32)
        distance = mj.mj_ray(
            model, data, np.array([0., 0, 0.015]), np.array([1., 0, 0]),
            np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, -1, hit,
        )
        self.assertEqual(hit[0], bar)
        self.assertAlmostEqual(distance, 0.48)
        for name in ["ramp", "rock", "odor_patch", "light_patch", "arena_wall_0"]:
            self.assertGreaterEqual(mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, name), 0)
        self.assertGreaterEqual(model.nlight, 1)


if __name__ == "__main__":
    unittest.main()
