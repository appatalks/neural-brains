import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fly_brain_worker import request_values
from fly_feeding import FeedingConfig
from fly_walking import Controls


class LiveFeedingTests(unittest.TestCase):
    def test_geometric_exposure_and_disable(self):
        config = FeedingConfig((0, 0, 0), 2, (0, 0, 0), 420)
        self.assertTrue(config.exposure([0, 0, 0])["sugar_contact"])
        self.assertTrue(config.exposure([2, 0, 0])["sugar_contact"])
        self.assertFalse(config.exposure([2.01, 0, 0])["sugar_contact"])
        self.assertFalse(config.exposure([0, 0, 0], False)["sugar_contact"])

    def test_invalid_config_does_not_default(self):
        original = json.loads((ROOT / "experiments/flywire-sugar/live-feeding.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            for key, value in [("source_radius_mm", 0), ("contact_stimulation_Hz", 150), ("seed", -1)]:
                with self.subTest(key=key):
                    path.write_text(json.dumps({**original, key: value}))
                    with self.assertRaises(ValueError):
                        FeedingConfig.load(path)
            path.write_text(json.dumps(original))
            self.assertEqual(FeedingConfig.load(path).seed, 420)

    def test_request_protocol_has_exact_intervals(self):
        self.assertEqual(request_values({"op": "step", "duration_ms": 16.7, "sugar_contact": True}),
                         ("step", 16.7, True))
        self.assertEqual(request_values({"op": "reset"}), ("reset", None, None))
        self.assertEqual(request_values({"op": "close"}), ("close", None, None))
        for invalid in [
            {"op": "step", "duration_ms": math.nan, "sugar_contact": True},
            {"op": "step", "duration_ms": 0.15, "sugar_contact": True},
            {"op": "step", "duration_ms": 1, "sugar_contact": 1},
            {"op": "step", "duration_ms": 1001, "sugar_contact": True},
            {"op": "reset", "silent": True}, {"op": "unknown"},
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                request_values(invalid)

    def test_sugar_switch_does_not_change_locomotion(self):
        controls = Controls()
        before = controls.motor_command()
        controls.key(ord("T"))
        self.assertFalse(controls.sugar_enabled)
        self.assertEqual(controls.motor_command(), before)
        controls.key(ord("T"))
        self.assertTrue(controls.sugar_enabled)

    def test_missing_brain_arguments_are_explicit(self):
        import fly_walking
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "provided together"):
                fly_walking.run(Path(temp) / "run", 0.5, True,
                                brain_feeding=ROOT / "experiments/flywire-sugar/live-feeding.json")

    def test_dashboard_requires_actual_neural_bridge(self):
        import fly_walking
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "dashboard requires"):
                fly_walking.run(Path(temp) / "run", 0.5, True, neural_dashboard=True)


if __name__ == "__main__":
    unittest.main()
