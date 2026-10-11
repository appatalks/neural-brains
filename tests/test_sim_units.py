import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sim_units import FLIGHT_UNITS, WALKING_UNITS, PhysicsUnits, simulation_steps


class UnitBoundaryTests(unittest.TestCase):
    def test_same_force_has_different_model_values(self):
        self.assertEqual(WALKING_UNITS.force_from_micro_newtons(5), 5)
        self.assertEqual(FLIGHT_UNITS.force_from_micro_newtons(5), 0.5)

    def test_length_conversion_roundtrip(self):
        for units in [WALKING_UNITS, FLIGHT_UNITS]:
            self.assertEqual(units.length_to_mm(units.length_from_mm(12)), 12)
        self.assertEqual(FLIGHT_UNITS.length_to_mm(1), 10)

    def test_signed_quantities_are_preserved(self):
        self.assertEqual(FLIGHT_UNITS.force_from_micro_newtons(-2), -0.2)
        self.assertEqual(FLIGHT_UNITS.length_from_mm(-10), -1)

    def test_invalid_quantities_rejected(self):
        with self.assertRaises(ValueError):
            PhysicsUnits(0, 1)
        for value in [math.nan, math.inf]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                FLIGHT_UNITS.force_from_micro_newtons(value)

    def test_exact_step_counts(self):
        self.assertEqual(simulation_steps(0.5, 0.0001), 5000)
        self.assertEqual(simulation_steps(0.5, 0.0002), 2500)
        self.assertEqual(simulation_steps(0.05, 0.0002), 250)

    def test_nonintegral_or_invalid_duration_rejected(self):
        for value in [0, math.nan, 0.0003]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                simulation_steps(value, 0.0002)


if __name__ == "__main__":
    unittest.main()
