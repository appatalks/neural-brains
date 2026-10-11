import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_flight_steering import select_dng02


class SteeringIdentityTests(unittest.TestCase):
    def row(self, label, root_id="123", side="left"):
        return {"cell_type": label, "root_id": root_id, "side": side, "hemibrain_type": ""}

    def test_explicit_subtypes_preserved_without_near_name_matches(self):
        rows = [self.row("DNg02_a"), self.row("DNg02_b", "124", "right"),
                self.row("DNg20", "125"), self.row("DNg02ish", "126")]
        selected = select_dng02(rows, {"123"})
        self.assertEqual([r["cell_type"] for r in selected], ["DNg02_a", "DNg02_b"])
        self.assertEqual([r["in_model"] for r in selected], [True, False])

    def test_absent_duplicate_and_ambiguous_candidates_rejected(self):
        for rows in [[], [self.row("DNg02"), self.row("DNg02_a")],
                     [self.row("DNg02_a", side="center")], [self.row("DNg02_a", root_id="invalid")]]:
            with self.assertRaises(ValueError):
                select_dng02(rows, {"123"})
