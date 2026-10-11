import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_performance import PhaseTimings


class PhaseTimingTests(unittest.TestCase):
    def test_totals_and_maximum_do_not_retain_samples(self):
        timing=PhaseTimings()
        with patch("fly_performance.time.perf_counter",side_effect=[0, .1, 1, 1.2]):
            with timing.measure("render"):
                pass
            with timing.measure("render"):
                pass
        row=timing.snapshot()["render"]
        self.assertEqual(row["calls"],2)
        self.assertAlmostEqual(row["seconds"],.3)
        self.assertAlmostEqual(row["maximum_seconds"],.2)
        self.assertAlmostEqual(row["mean_ms"],150)
        row["calls"]=100
        self.assertEqual(timing.snapshot()["render"]["calls"],2)

    def test_failed_phase_is_measured_and_error_propagates(self):
        timing=PhaseTimings()
        with self.assertRaises(RuntimeError):
            with timing.measure("physics"):
                raise RuntimeError("failure")
        self.assertEqual(timing.snapshot()["physics"]["calls"],1)
