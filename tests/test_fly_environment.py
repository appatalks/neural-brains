import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fly_environment as environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "experiments/fly-walking/habitat.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "scene.json"

    def load(self):
        self.path.write_text(json.dumps(self.config))
        return environment.Environment.load(self.path)

    def test_habitat_and_saved_schema_roundtrip(self):
        scene = self.load()
        self.assertEqual(len(scene.terrain), 3)
        self.assertEqual(scene.half_size_mm, 30)
        self.config = environment.environment_dict(scene)
        self.assertEqual(self.load(), scene)

    def test_invalid_sizes_and_nonfinite_values(self):
        for value in [0, -1, math.nan, math.inf, True]:
            with self.subTest(value=value):
                self.config["range_limit_mm"] = value
                with self.assertRaises(ValueError):
                    self.load()

    def test_unknown_fields_are_not_silent(self):
        self.config["temperature"] = 25
        with self.assertRaises(ValueError):
            self.load()

    def test_malformed_scene_and_schedule(self):
        self.path.write_text("[]")
        with self.assertRaises(ValueError):
            environment.Environment.load(self.path)
        self.path.write_text("[1]")
        with self.assertRaises(ValueError):
            environment.load_schedule(self.path)

    def test_invalid_source_and_duplicate_name(self):
        self.config["odors"][0]["spread_mm"] = 0
        with self.assertRaises(ValueError):
            self.load()
        self.config["odors"][0]["spread_mm"] = 1
        self.config["odors"][0]["name"] = self.config["terrain"][0]["name"]
        with self.assertRaises(ValueError):
            self.load()

    def test_terrain_stays_inside_arena(self):
        self.config["terrain"][0]["position_mm"][0] = 100
        with self.assertRaises(ValueError):
            self.load()

    def test_chemical_field_and_distance(self):
        source = environment.Source("test", (0, 0, 0), 1, 2)
        self.assertEqual(source.value_at((0, 0, 0)), 1)
        self.assertAlmostEqual(source.value_at((2, 0, 0)), math.exp(-0.5))
        self.assertGreater(source.value_at((1, 0, 0)), source.value_at((4, 0, 0)))

    def test_drag_opposes_relative_velocity_and_is_capped(self):
        scene = self.load()
        self.assertEqual(scene.wind_force(scene.wind_mm_s), (0, 0, 0))
        force = scene.wind_force((10000, 0, 0))
        self.assertLess(force[0], 0)
        self.assertAlmostEqual(math.sqrt(sum(x*x for x in force)), scene.drag_limit_uN)

    def observation(self, **changes):
        values = dict(
            time_s=0, episode=0, position_mm=(0, 0, 1), velocity_mm_s=(0, 0, 0),
            odor_left=0, odor_right=0, light_left=0, light_right=0,
            range_left_mm=12, range_forward_mm=12, range_right_mm=12,
            joint_angles_rad=(), joint_velocities_rad_s=(), contacts=0,
        )
        values.update(changes)
        return environment.Observation(**values)

    def test_sensory_policy_motor_direction(self):
        straight = environment.sensory_command(self.observation(), 1)
        self.assertEqual(straight, environment.MotorCommand(1, 1))
        odor_left = environment.sensory_command(self.observation(odor_left=1), 1)
        self.assertGreater(odor_left.right_drive, odor_left.left_drive)
        blocked = environment.sensory_command(
            self.observation(range_forward_mm=0.5, range_left_mm=12, range_right_mm=1), 1
        )
        self.assertGreater(blocked.right_drive, blocked.left_drive)

    def test_avoidance_starts_before_wall_contact(self):
        approach = environment.sensory_command(
            self.observation(range_forward_mm=4, range_left_mm=12, range_right_mm=1), 1
        )
        self.assertGreater(approach.right_drive, approach.left_drive)
        self.assertEqual(approach.left_drive, 0)

    def test_side_clearance_and_fallen_state(self):
        side = environment.sensory_command(
            self.observation(range_forward_mm=12, range_left_mm=12, range_right_mm=1), 1
        )
        self.assertGreater(side.right_drive, side.left_drive)
        self.assertEqual(
            environment.sensory_command(self.observation(uprightness=-0.5), 1),
            environment.MotorCommand(0, 0),
        )

    def test_real_visual_channel_changes_motor_command(self):
        dark = environment.sensory_command(self.observation(
            visual_activity_left=0.1, visual_activity_right=0.1,
        ), 1)
        bright_left = environment.sensory_command(self.observation(
            visual_activity_left=0.9, visual_activity_right=0.1,
        ), 1)
        self.assertNotEqual(dark, bright_left)
        self.assertGreater(bright_left.right_drive, bright_left.left_drive)
        with self.assertRaises(ValueError):
            environment.sensory_command(self.observation(
                visual_activity_left=2, visual_activity_right=0.1,
            ), 1)

    def test_unsupported_flight_and_invalid_motors_rejected(self):
        with self.assertRaisesRegex(ValueError, "flight"):
            environment.MotorCommand(1, 1, "fly")
        for value in [-1, 2, math.nan]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                environment.MotorCommand(value, 1)

    def test_schedule_is_sorted_and_pause_not_allowed(self):
        self.path.write_text(json.dumps([{"time_s": 0.5, "key": "B"}, {"time_s": 0.4, "key": "F"}]))
        with self.assertRaises(ValueError):
            environment.load_schedule(self.path)
        self.path.write_text(json.dumps([{"time_s": 0.5, "key": "P"}]))
        with self.assertRaises(ValueError):
            environment.load_schedule(self.path)
        self.assertEqual(len(environment.load_schedule(ROOT / "experiments/fly-walking/perturbations.json")), 5)


if __name__ == "__main__":
    unittest.main()
