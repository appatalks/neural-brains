import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_takeoff_circuit import population, select_neurons


class TakeoffIdentityTests(unittest.TestCase):
    def row(self, root, cell="", hemibrain="", side=""):
        return {"root_id": root, "cell_type": cell, "hemibrain_type": hemibrain, "side": side}

    def rows(self):
        return [
            self.row("1", "DNp01", "Giant Fiber", "left"),
            self.row("2", "DNp01", "Giant Fiber", "right"),
            self.row("3", hemibrain="LC4", side="left"),
            self.row("4", hemibrain="LPLC2", side="right"),
        ]

    def test_exact_labels_avoid_lc40_lc45(self):
        for label in ["LC40a,LC40b", "LC45a", "LC4_candidate", "LPLC20"]:
            self.assertIsNone(population(self.row("9", hemibrain=label)))
        self.assertEqual(population(self.row("3", hemibrain="LC4")), "LC4")

    def test_missing_ids_are_retained_not_remapped(self):
        result = select_neurons(self.rows(), {"1", "2", "3"})
        self.assertEqual([row["root_id"] for row in result if not row["in_model"]], ["4"])

    def test_giant_fiber_requires_both_annotation_labels(self):
        self.assertIsNone(population(self.row("1", "DNp01", "unknown")))
        self.assertIsNone(population(self.row("1", "", "Giant Fiber")))

    def test_duplicate_or_missing_population_fails(self):
        with self.assertRaises(ValueError):
            select_neurons(self.rows() + [self.rows()[0]], {"1", "2", "3", "4"})
        with self.assertRaises(ValueError):
            select_neurons(self.rows()[:-1], {"1", "2", "3"})
