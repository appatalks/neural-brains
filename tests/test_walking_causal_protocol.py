import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from test_walking_causality import CASES, SUGAR_CASES, evaluate, evaluate_sugar


class WalkingCausalProtocolTests(unittest.TestCase):
    def sugar_rows(self):
        rows = []
        for case, active, cut, clamp, _ in SUGAR_CASES:
            counts = {name: 0 for name in ("P9", "BPN", "sugar", "FG", "BB", "BDN2", "oDN1")}
            for source in ("P9", "BPN", "sugar"):
                counts[source] = 100 if source in active else 0
            counts["oDN1"] = 20 if "P9" in active else 0
            counts["BDN2"] = 100 if "BPN" in active else 0
            if "sugar" in active:
                counts["FG"], counts["BB"] = 20, 1
                counts["oDN1"] = 5 if "P9" in active else 0
                counts["BDN2"] = 40 if "BPN" in active else 0
            if cut == "FG" or clamp == "silence:FG":
                counts["oDN1"] = 15 if "P9" in active else 0
                counts["BDN2"] = 90 if "BPN" in active else 0
            if clamp == "silence:FG":
                counts["FG"] = 0
            if cut == "sugar":
                counts = {**dict.fromkeys(counts, 0), "sugar": 100}
            source = "P9" if "P9" in active else "BPN" if "BPN" in active else "other"
            rows.append({"seed": 420, "case": case, "population_spikes": counts,
                         "network_spikes": sum(counts.values()), "mn9_spikes": 0,
                         "counts_sha256": source+"-sugar"})
        return rows

    def test_sugar_causal_checks_and_retained_equal_count_negative_result(self):
        rows = self.sugar_rows()
        self.assertTrue(all(row["passed"] for row in evaluate_sugar(rows)))
        for case in ("P9-sugar-FGcut", "P9-sugar-FGsilence"):
            next(row for row in rows if row["case"] == case)["population_spikes"]["oDN1"] = 5
        failed = [row for row in evaluate_sugar(rows) if not row["passed"]]
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(row["check"].startswith("P9 FG") for row in failed))

    def test_sugar_protocol_requires_complete_results(self):
        with self.assertRaises(ValueError):
            evaluate_sugar(self.sugar_rows()[:-1])

    def rows(self):
        rows = []
        for case, active, cut, clamp, delayed in CASES:
            counts = {name: 0 for name in ("P9", "BPN", "BDN2", "oDN1")}
            counts["P9"] = 100 if "P9" in active else 0
            counts["BPN"] = 100 if "BPN" in active else 0
            counts["oDN1"] = 20 if "P9" in active else 0
            counts["BDN2"] = 100 if "BPN" in active or "BDN2" in active else 0
            if "FG" in active:
                counts["oDN1"], counts["BDN2"] = 1, 1
            if "BB" in active:
                counts["oDN1"], counts["BDN2"] = 0, 50
            if cut is not None:
                counts["oDN1"], counts["BDN2"] = 0, 0
            if clamp and clamp.startswith("silence:"):
                counts[clamp.split(":")[1]] = 0
            source = "P9" if "P9" in active else "BPN" if "BPN" in active else "other"
            halves = [{"counts_sha256": source+"-half", "population_spikes": {
                name: value//2 for name, value in counts.items()}} for _ in range(2)]
            if delayed:
                halves[1] = copy.deepcopy(halves[1])
                halves[1]["population_spikes"]["oDN1"] = 1
                halves[1]["population_spikes"]["BDN2"] = 1
            rows.append({
                "seed": 420, "case": case, "population_spikes": counts,
                "network_spikes": sum(counts.values()), "counts_sha256": source,
                "halves": halves,
            })
        return rows

    def test_all_predeclared_causal_checks_pass_for_valid_fixture(self):
        checks = evaluate(self.rows())
        self.assertEqual(len(checks), 19)
        self.assertTrue(all(row["passed"] for row in checks))

    def test_source_cut_direct_clamp_and_sham_failures_are_reported(self):
        for case, field, value in (
            ("P9-cut", "network_spikes", 101),
            ("BDN2-direct-silence", "network_spikes", 1),
            ("BPN-sham", "counts_sha256", "different"),
        ):
            rows = self.rows()
            next(row for row in rows if row["case"] == case)[field] = value
            with self.subTest(case=case):
                self.assertTrue(any(not row["passed"] for row in evaluate(rows)))

    def test_missing_duplicate_and_extra_cases_are_rejected(self):
        for change in ("missing", "duplicate", "extra"):
            rows = self.rows()
            if change == "missing":
                rows.pop()
            elif change == "duplicate":
                rows.append(copy.deepcopy(rows[0]))
            else:
                rows.append({**rows[0], "case": "invented"})
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluate(rows)
