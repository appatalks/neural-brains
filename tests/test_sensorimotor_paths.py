import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_sensorimotor_paths import CANDIDATE_TYPES, select_candidates, select_manc_matches


class SensorimotorIdentityTests(unittest.TestCase):
    def manc_rows(self):
        return [
            {"bodyid": str(i*2+j+10), "group": str(i), "type": label,
             "systematic_type": f"DNtest{i}", "side": side, "confidence_1_5": "3"}
            for i, label in enumerate(CANDIDATE_TYPES) for j, side in enumerate(["L", "R"])
        ]

    def test_primary_manc_identity_namespace_and_confidence_preserved(self):
        result = select_manc_matches(self.manc_rows())
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0]["side"], "left")
        self.assertEqual(result[0]["manc_body_id"], "10")
        self.assertEqual(result[0]["published_matching_confidence_1_5"], 3)
        self.assertNotIn("root_id", result[0])

    def test_primary_manc_missing_side_confidence_duplicate_rejected(self):
        for field, value in [("side", "center"), ("confidence_1_5", "7"), ("bodyid", "invalid")]:
            rows = self.manc_rows()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_manc_matches(rows)
        rows = self.manc_rows()
        rows.append(rows[0])
        with self.assertRaises(ValueError):
            select_manc_matches(rows)
        with self.assertRaises(ValueError):
            select_manc_matches(self.manc_rows()[:-1])

    def rows(self):
        return [
            {"root_id": str(i*2+j+100), "cell_type": label if label.startswith("DNa") else "",
             "hemibrain_type": label if label.startswith("DNp") else "other",
             "side": side}
            for i, label in enumerate(CANDIDATE_TYPES) for j, side in enumerate(["left", "right"])
        ]

    def test_both_annotation_fields_and_sides_preserved(self):
        rows = self.rows()
        result = select_candidates(rows, {r["root_id"] for r in rows})
        self.assertEqual(len(result), 8)
        self.assertTrue(all(r["in_model"] for r in result))
        self.assertEqual(result[4]["matched_field"], "hemibrain_type")
        self.assertEqual(result[0]["matched_field"], "cell_type")

    def test_missing_side_conflicting_type_and_duplicate_rejected(self):
        for change in ["missing", "side", "conflict", "duplicate"]:
            rows = self.rows()
            if change == "missing":
                rows.pop()
            elif change == "side":
                rows[0]["side"] = "center"
            elif change == "conflict":
                rows[0]["hemibrain_type"] = "DNp07"
            else:
                rows.append(rows[0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_candidates(rows, set())

    def test_near_names_do_not_replace_missing_types(self):
        rows = self.rows()
        rows[0]["cell_type"] = "DNa040"
        with self.assertRaises(ValueError):
            select_candidates(rows, set())

    def test_conflicting_historical_steering_alias_is_reported_not_merged(self):
        rows = self.rows()
        rows.extend([
            {"root_id": "200", "cell_type": "DNae004", "hemibrain_type": "DNa04", "side": "left"},
            {"root_id": "201", "cell_type": "DNae004", "hemibrain_type": "DNa04", "side": "right"},
        ])
        result = select_candidates(rows, {r["root_id"] for r in rows})
        group = [r for r in result if r["population"] == "DNa04"]
        self.assertEqual(len(group), 4)
        self.assertTrue(all(r["ambiguous_type_correspondence"] for r in group))
        self.assertEqual({r["cell_type"] for r in group}, {"DNa04", "DNae004"})
