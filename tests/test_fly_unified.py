import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_unified import evaluate_motor, named_indices


class UnifiedMotorTests(unittest.TestCase):
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
