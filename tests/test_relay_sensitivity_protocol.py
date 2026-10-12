import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from test_relay_sensitivity import candidates, select_candidate, DEVELOPMENT, HELD_OUT


class RelayUncertaintyProtocolTests(unittest.TestCase):
    def test_grid_preserves_the_old_hypothesis_and_has_fixed_distinct_candidates(self):
        grid = candidates()
        self.assertEqual(len(grid), 9)
        self.assertEqual(len({row["id"] for row in grid}), 9)
        original = next(row for row in grid if row["mean_drive_at_100Hz"] == 250 and row["decay_s"] == .04)
        self.assertEqual(original["current_per_spike"], 62.5)
        for row in grid:
            self.assertAlmostEqual(row["current_per_spike"]*100*row["decay_s"], row["mean_drive_at_100Hz"])
        self.assertFalse(set(DEVELOPMENT) & set(HELD_OUT))
        self.assertEqual(HELD_OUT, (431, 432))

    def test_selection_uses_only_passed_development_candidates_and_a_fixed_preference(self):
        grid = candidates()
        checks = [
            {"seed": seed, "check": label, "passed": True}
            for seed in DEVELOPMENT for label in
            ("matched response", "matched FG suppression", "physical bounds",
             "causal delivery", "legacy response")
        ]
        rows = [{"candidate": row, "passed": True, "checks": copy.deepcopy(checks)} for row in grid]
        chosen = select_candidate(rows)
        self.assertEqual(chosen["id"], "mean-250-tau-40")
        old = copy.deepcopy(chosen)
        next(row for row in rows if row["candidate"]["id"] == old["id"])["passed"] = False
        chosen = select_candidate(rows)
        self.assertNotEqual(chosen["id"], old["id"])
        self.assertEqual(select_candidate(list(reversed(rows))), chosen)
        self.assertIsNone(select_candidate([{**row, "passed": False} for row in rows]))
        self.assertIsNone(select_candidate([{"candidate": grid[0], "passed": True, "checks": []}]))
        incomplete = copy.deepcopy(rows[0])
        incomplete["checks"][0]["passed"] = False
        self.assertIsNone(select_candidate([incomplete]))
