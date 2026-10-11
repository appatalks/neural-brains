import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("fly_walking", ROOT / "scripts/fly_walking.py")
walking = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = walking
spec.loader.exec_module(walking)


class WalkingControlsTests(unittest.TestCase):
    def test_eye_inset_is_top_right_and_resizes(self):
        self.assertEqual(walking.eye_inset_bounds(0, 0, 1000, 800), (670, 630, 320, 160))
        x, y, width, height = walking.eye_inset_bounds(100, 50, 200, 100)
        self.assertGreaterEqual(x, 100)
        self.assertGreaterEqual(y, 50)
        self.assertLessEqual(x + width, 300)
        self.assertLessEqual(y + height, 150)
        with self.assertRaises(ValueError):
            walking.eye_inset_bounds(0, 0, 0, 100)

    def test_drive_and_turn_limits(self):
        controls = walking.Controls()
        for _ in range(100):
            controls.key(ord("W"))
            controls.key(ord("D"))
        self.assertEqual(controls.drive, 1.5)
        self.assertEqual(controls.turn, 0.8)
        self.assertTrue(all(0 <= value <= 1.5 for value in controls.signal()))
        for _ in range(100):
            controls.key(ord("S"))
            controls.key(ord("A"))
        self.assertEqual(controls.drive, 0)
        self.assertEqual(controls.turn, -0.8)

    def test_toggles(self):
        controls = walking.Controls()
        for key in "POF":
            controls.key(ord(key))
        self.assertTrue(controls.paused)
        self.assertFalse(controls.obstacles)
        self.assertTrue(controls.slippery)
        controls.key(ord("D"))
        controls.key(ord("X"))
        self.assertEqual(controls.turn, 0)
        controls.key(ord("N"))
        self.assertTrue(controls.sensory)
        controls.key(ord("N"))
        self.assertFalse(controls.sensory)
        self.assertFalse(controls.follow_camera)
        controls.key(ord("C"))
        self.assertTrue(controls.follow_camera)
        controls.key(ord("C"))
        self.assertFalse(controls.follow_camera)

    def test_playback_and_unknown_keys(self):
        controls = walking.Controls()
        for _ in range(100):
            controls.key(ord("["))
        self.assertEqual(controls.playback, 0.1)
        for _ in range(100):
            controls.key(ord("]"))
        self.assertEqual(controls.playback, 2)
        self.assertIsNone(controls.key(1000))
        self.assertEqual(controls.key(ord("R")), "R")
        self.assertEqual(controls.key(ord("B")), "B")
        self.assertEqual(controls.key(ord("Q")), "Q")

    def test_headless_cannot_request_unbounded_session(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "interactive viewer"):
                walking.run(Path(temp) / "run", 0.5, True, until_closed=True)

    def test_outputs_are_external_and_not_overwritten(self):
        with self.assertRaises(ValueError):
            walking.external_output(ROOT / "results")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                walking.external_output(Path(temp))
            self.assertEqual(walking.external_output(Path(temp) / "new"), Path(temp) / "new")


if __name__ == "__main__":
    unittest.main()
