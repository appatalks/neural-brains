import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_touch_state_paths import inventory, select_targets


class TouchStateIdentityTests(unittest.TestCase):
    def fixture(self):
        rows = []
        primary = []
        for pair, name in enumerate(("MDN1, MDN2", "MDN3, MDN4")):
            source = {"E": name, "D": "DNp50"}
            for column, side in (("A", "left"), ("B", "right")):
                root = str(720575940600000000+len(rows))
                source[column] = root
                rows.append({"root_id": root, "side": side, "hemibrain_type": "MDN",
                             "cell_type": "DNpe078", "super_class": "descending",
                             "cell_class": "DN", "cell_sub_class": "", "top_nt": "acetylcholine",
                             "top_nt_conf": ".9"})
            primary.append(source)
        for side in ("left", "right"):
            rows.append({"root_id": str(720575940600000000+len(rows)), "side": side,
                         "hemibrain_type": "OA-VPM4", "cell_type": "", "super_class": "central",
                         "cell_class": "", "cell_sub_class": "", "top_nt": "octopamine",
                         "top_nt_conf": ".63"})
        return rows, {row["root_id"] for row in rows}, primary

    def test_exact_primary_mdn_and_annotated_feeding_candidates_are_kept_separate(self):
        rows, ids, primary = self.fixture()
        targets = select_targets(rows, ids, primary)
        self.assertEqual(len(targets), 6)
        self.assertEqual(sum(row["population"] == "MDN" for row in targets), 4)
        self.assertEqual(sum(row["population"] == "OA-VPM4" for row in targets), 2)
        self.assertEqual(targets[0]["root_id"], rows[0]["root_id"])
        self.assertEqual(targets[0]["primary_cell_type"], "DNp50")
        self.assertIn("feeding", targets[-1]["scope"])

    def test_missing_model_side_conflict_wrong_alias_and_duplicate_primary_rejected(self):
        for case in ("model", "side", "alias", "duplicate", "oa-side", "oa-nt"):
            rows, ids, primary = self.fixture()
            if case == "model":
                ids.remove(rows[0]["root_id"])
            elif case == "side":
                rows[0]["side"] = "right"
            elif case == "alias":
                rows[0]["hemibrain_type"] = "MDN-similar"
            elif case == "duplicate":
                primary[1]["A"] = primary[0]["A"]
            elif case == "oa-side":
                rows[-1]["side"] = "left"
            else:
                rows[-1]["top_nt"] = "unknown"
            with self.subTest(case=case), self.assertRaises(ValueError):
                select_targets(rows, ids, primary)

    def test_missing_tla_is_reported_not_inferred_from_generic_ascending_cells(self):
        rows, ids, _ = self.fixture()
        generic = copy.deepcopy(rows[0])
        generic.update({"root_id": "99", "super_class": "ascending", "cell_class": "AN",
                        "cell_type": "", "hemibrain_type": ""})
        rows.append(generic)
        report = inventory(rows, ids)
        self.assertEqual(report["ascending"]["annotation_rows"], 1)
        self.assertEqual(report["ascending"]["matched_model"], 0)
        self.assertEqual(report["exact_label_matches"]["TLA"], [])
        self.assertEqual(report["exact_label_matches"]["TwoLumps"], [])

    def test_octopamine_prediction_does_not_turn_non_neurons_into_drive_targets(self):
        rows, ids, _ = self.fixture()
        glia = copy.deepcopy(rows[-1])
        glia.update({"root_id": "99", "super_class": "not_a_neuron",
                     "cell_type": "", "hemibrain_type": "", "cell_class": "glia"})
        rows.append(glia)
        result = inventory(rows, ids)["predicted_octopamine"]
        self.assertEqual(result["annotation_rows"], 3)
        self.assertEqual(result["matched_model"], 2)
        self.assertEqual(result["non_neuron_annotation_rows"], 1)
