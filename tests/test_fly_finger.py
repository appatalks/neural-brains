import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_finger import Looming, Pointer, pointer_target
from fly_walking import Controls


class FingerTests(unittest.TestCase):
    def test_window_match_requires_both_pid_and_title(self):
        with patch("fly_finger.subprocess.check_output", return_value="123\n") as call:
            pointer = Pointer()
        self.assertEqual(pointer.window, "123")
        self.assertIn("--all", call.call_args.args[0])
        self.assertIn("--sync", call.call_args.args[0])
        self.assertEqual(call.call_args.kwargs["timeout"], 10)

    def test_approach_not_static_distance_triggers_encoder(self):
        looming = Looming()
        self.assertFalse(looming.sample(10, 1.5, 0.1, True)["looming_active"])
        self.assertTrue(looming.sample(8, 1.5, 0.1, True)["looming_active"])
        self.assertFalse(looming.sample(8, 1.5, 0.1, True)["looming_active"])
        self.assertFalse(looming.sample(10, 1.5, 0.1, True)["looming_active"])
        self.assertFalse(looming.sample(1, 1.5, 0.1, False)["looming_active"])

    def test_hand_is_an_environment_control(self):
        controls = Controls(autonomous=True)
        before = controls.motor_command()
        self.assertEqual(controls.key(ord("H")), "H")
        self.assertTrue(controls.finger_enabled)
        self.assertEqual(controls.motor_command(), before)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "Requires simulation environment")
    def test_projection_to_horizontal_arena_plane(self):
        import numpy as np
        camera = SimpleNamespace(
            pos=[0, 0, 10], forward=[0, 0, -1], up=[0, 1, 0],
            frustum_near=1, frustum_bottom=-1, frustum_top=1,
        )
        viewport = SimpleNamespace(left=0, bottom=0, width=100, height=100)
        np.testing.assert_allclose(pointer_target(camera, viewport, 50, 50), [0, 0, 1.5])
        self.assertIsNone(pointer_target(camera, viewport, -10, 50))
        camera.frustum_center = 0.1
        np.testing.assert_allclose(pointer_target(camera, viewport, 50, 50), [0.85, 0, 1.5])


if __name__ == "__main__":
    unittest.main()
