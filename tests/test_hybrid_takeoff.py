import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_takeoff import launch_state, assisted_force


class HybridTakeoffTests(unittest.TestCase):
    def test_actual_gf_gate_and_assistance_handoff(self):
        self.assertEqual(launch_state({"gf": 0}, None), "grounded")
        self.assertEqual(launch_state({"gf": 1}, None), "launch")
        self.assertEqual(launch_state({}, 0.299), "launch")
        self.assertEqual(launch_state({}, 0.3), "flight")
        with self.assertRaises(ValueError):
            launch_state({"gf": -1}, None)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "Requires NumPy")
    def test_assistance_force_is_bounded_and_does_not_assign_pose(self):
        import numpy as np
        position = np.array([0., 0, .15])
        before = position.copy()
        wrench = assisted_force(0.001, position, np.zeros(6), np.eye(3), np.eye(3),
                                np.array([0., 0, 1]))
        self.assertEqual(wrench.shape, (6,))
        self.assertTrue((abs(wrench[:3]) <= 4 * .001 * 981).all())
        self.assertGreater(wrench[2], 0)
        np.testing.assert_array_equal(before, position)


if __name__ == "__main__":
    unittest.main()
