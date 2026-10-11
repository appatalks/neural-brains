import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_recovery import Recovery


class RecoveryStateTests(unittest.TestCase):
    def test_requires_sustained_uprightness(self):
        recovery = Recovery()
        self.assertEqual(recovery.update(0, -1), "push")
        self.assertEqual(recovery.update(0.3, 0.9), "stabilize")
        recovery.update(0.4, 0.9)
        recovery.update(0.6, -0.2)
        self.assertEqual(recovery.successes, 0)
        recovery.update(0.7, 0.9)
        self.assertEqual(recovery.update(1.21, 0.9), "idle")
        self.assertEqual(recovery.successes, 1)
        self.assertEqual(recovery.attempts, 1)

    def test_failed_recovery_is_not_silent_or_reset(self):
        recovery = Recovery()
        recovery.update(0, -1)
        recovery.update(0.3, -1)
        self.assertEqual(recovery.update(2.4, -1), "failed")
        self.assertEqual(recovery.failures, 1)
        recovery.update(3, -1)
        self.assertEqual(recovery.attempts, 1)
        recovery.reset(4)
        self.assertEqual(recovery.phase, "idle")

    def test_upright_walk_never_starts_recovery(self):
        recovery = Recovery()
        for time in [0, 1, 2]:
            recovery.update(time, 1)
        self.assertEqual(recovery.phase, "idle")
        self.assertEqual(recovery.attempts, 0)
