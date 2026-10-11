import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_pointer_motion import capped_motion


class PointerMotionTests(unittest.TestCase):
    def test_wall_time_cap_is_not_simulation_throughput_dependent(self):
        self.assertEqual(capped_motion([0, 0, 0], [10, 0, 0], .05), [1, 0, 0])
        self.assertEqual(capped_motion([0, 0, 0], [10, 0, 0], 10), [2, 0, 0])
        self.assertEqual(capped_motion([0, 0, 0], [.5, 0, 0], .05), [.5, 0, 0])

    def test_zero_time_or_zero_distance_does_not_move(self):
        self.assertEqual(capped_motion([1, 2, 3], [9, 2, 3], 0), [1, 2, 3])
        self.assertEqual(capped_motion([1, 2, 3], [1, 2, 3], .1), [1, 2, 3])

    def test_invalid_inputs_rejected(self):
        for position, target, duration in [
            ([0, 0], [1, 2, 3], .1), ([0, 0, 0], [float("nan"), 0, 0], .1),
            ([0, 0, 0], [1, 0, 0], -1), ([0, 0, 0], [1, 0, 0], float("inf")),
        ]:
            with self.assertRaises(ValueError):
                capped_motion(position, target, duration)
