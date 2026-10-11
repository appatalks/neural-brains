import sys
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fly_habitat
from fly_walking import Controls, control_help


class AutonomousHabitatTests(unittest.TestCase):
    def test_no_direct_steering_or_mode_changes(self):
        controls = Controls(autonomous=True)
        before = controls.motor_command()
        for key in "WSADXN":
            self.assertIsNone(controls.key(ord(key)))
        self.assertEqual(controls.motor_command(), before)
        self.assertTrue(controls.sensory)
        self.assertEqual(controls.turn, 0)

    def test_environment_and_session_controls_remain(self):
        controls = Controls(autonomous=True)
        for key in "TOFBCPRQ":
            self.assertEqual(controls.key(ord(key)), key)
        self.assertFalse(controls.sugar_enabled)
        self.assertFalse(controls.obstacles)
        self.assertTrue(controls.slippery)

    def test_help_discloses_hybrid_without_manual_modes(self):
        text = control_help(True)
        self.assertNotIn("N sensory-demo", text)
        self.assertNotIn("W/S drive", text)
        self.assertIn("actual FlyWire", text)
        self.assertIn("engineered", text)

    def test_main_launches_same_automatic_components(self):
        with patch.object(fly_habitat, "run") as run:
            self.assertEqual(fly_habitat.main(["--data-dir", "/tmp/test-data", "--output-dir", "/tmp/test-results"]), 0)
            params = run.call_args.kwargs
            for field in ["sensory", "until_closed", "vision", "self_righting", "autonomous"]:
                self.assertTrue(params[field])
            self.assertTrue(str(params["brain_feeding"]).endswith("live-feeding.json"))

    def test_bounded_launch_keeps_autonomy(self):
        with patch.object(fly_habitat, "run") as run:
            self.assertEqual(fly_habitat.main([
                "--data-dir", "/tmp/test-data", "--output-dir", "/tmp/test-results",
                "--headless", "--seconds", "0.2",
            ]), 0)
            self.assertFalse(run.call_args.kwargs["until_closed"])
            self.assertTrue(run.call_args.kwargs["autonomous"])

    def test_main_has_no_controller_or_drive_option(self):
        for flag, value in [("--controller", "manual"), ("--drive", "0")]:
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    fly_habitat.main([
                        "--data-dir", "/tmp/test-data", "--output-dir", "/tmp/test-results",
                        flag, value,
                    ])
                self.assertEqual(result.exception.code, 2)

    def test_failed_component_never_becomes_silent_fallback(self):
        with patch.object(fly_habitat, "run", side_effect=RuntimeError("brain unavailable")):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(fly_habitat.main([
                    "--data-dir", "/tmp/test-data", "--output-dir", "/tmp/test-results",
                ]), 1)
            self.assertIn("brain unavailable", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
