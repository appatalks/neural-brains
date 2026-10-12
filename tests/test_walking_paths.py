import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_walking_paths import CORE_NAMES, SHEETS, primary_populations, read_identity_rows, select_candidates


class WalkingPathTests(unittest.TestCase):
    def primary_fixture(self):
        flywire = [{"A": "ID_left", "B": "ID_right", "E": "Name in this study"}]
        annotations = {}
        for name, pairs in (("P9", 1), ("BPN", 6), ("FG", 1), ("BB", 1),
                            ("BDN2", 1), ("oDN1", 1), ("BRK", 3)):
            for pair in range(pairs):
                row = {"E": f"BRK{pair*2+1}, BRK{pair*2+2}" if name == "BRK" else name}
                if name == "BPN":
                    row.update({"C": "Type 1 BPN", "D": "CL210"})
                for column, side in (("A", "left"), ("B", "right")):
                    root_id = str(720575940600000000+len(annotations))
                    row[column] = root_id
                    annotations[root_id] = {"side": side, "cell_type": "candidate",
                                            "hemibrain_type": "", "top_nt": "acetylcholine"}
                flywire.append(row)
        return {"FlyWire": flywire, "FANC+MANC": [
            {"A": "FANC_ID_left", "B": "FANC_ID_right", "C": "MANC_ID_left",
             "D": "MANC_ID_right", "F": "Name in this study"}]}, annotations

    def test_primary_table_resolves_canonical_sides_and_separate_populations(self):
        sheets, annotations = self.primary_fixture()
        with patch("audit_walking_paths.read_workbook_sheets", return_value=sheets):
            populations, vnc_rows = primary_populations(Path("/unused"), annotations, set(annotations))
        self.assertEqual(len(populations["BPN"]), 12)
        self.assertEqual(len(populations["BRK"]), 6)
        self.assertEqual(populations["BDN2"][0]["side"], "left")
        self.assertEqual(vnc_rows, [])

    def test_primary_missing_ids_side_conflicts_and_wrong_bpn_class_rejected(self):
        for case in ("missing", "side", "bpn"):
            sheets, annotations = self.primary_fixture()
            model_ids = set(annotations)
            if case == "missing":
                model_ids.pop()
            elif case == "side":
                annotations[next(iter(annotations))]["side"] = "right"
            else:
                next(row for row in sheets["FlyWire"] if row.get("E") == "BPN")["D"] = "SMP461"
            with self.subTest(case=case), patch("audit_walking_paths.read_workbook_sheets", return_value=sheets):
                with self.assertRaises(ValueError):
                    primary_populations(Path("/unused"), annotations, model_ids)

    def rows(self):
        names = sorted(CORE_NAMES | {f"BPN_1{letter}" for letter in "abcdef"})
        return [
            {"name": name, "root_id": str(720575940600000000+i*2+j),
             "workbook_side": side, "worksheet": "walk", "comment": ""}
            for i, name in enumerate(names) for j, side in enumerate(("left", "right"))
        ]

    def annotations(self, rows):
        return {
            row["root_id"]: {"side": "right" if row["workbook_side"] == "left" else "left",
                             "cell_type": "candidate", "hemibrain_type": "", "top_nt": "acetylcholine"}
            for row in rows
        }

    def test_exact_ids_side_conflicts_and_unresolved_alias_preserved(self):
        rows = self.rows()
        selected = select_candidates(rows, self.annotations(rows), {row["root_id"] for row in rows})
        self.assertEqual(len(selected), 24)
        self.assertTrue(all(row["side_conflict"] and row["in_model"] for row in selected))
        self.assertEqual(selected[0]["root_id"], rows[0]["root_id"])
        self.assertEqual(sum(row["paper_alias_unresolved"] for row in selected), 2)
        self.assertNotIn("motor_gain", selected[0])

    def test_missing_model_and_annotations_are_reported_without_substitution(self):
        selected = select_candidates(self.rows(), {}, set())
        self.assertTrue(all(not row["in_model"] and not row["annotation_present"] for row in selected))
        self.assertTrue(all(row["annotation_side"] is None for row in selected))
        self.assertTrue(all(row["predicted_nt"] is None for row in selected))

    def test_invalid_duplicate_missing_and_near_name_candidates_rejected(self):
        for change in ("rounded", "duplicate", "missing", "near_name", "side"):
            rows = self.rows()
            if change == "rounded":
                rows[0]["root_id"] = "7.205759406e17"
            elif change == "duplicate":
                rows[1]["root_id"] = rows[0]["root_id"]
            elif change == "missing":
                rows.pop()
            elif change == "near_name":
                rows[0]["name"] += "_similar"
            else:
                rows[0]["workbook_side"] = "center"
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_candidates(rows, {}, set())

    def write_workbook(self, path, formula=False, invalid_header=False, missing_sheet=False):
        namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        relations = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        strings = ["Name", "ID_left", "ID_right", "FG", "720575940611160930", "720575940628755815"]
        with ZipFile(path, "w") as workbook:
            root = ET.Element("sst", xmlns=namespace)
            for string in strings:
                ET.SubElement(ET.SubElement(root, "si"), "t").text = string
            workbook.writestr("xl/sharedStrings.xml", ET.tostring(root))
            sheets = "".join(
                f'<sheet name="{name}" sheetId="{index+10}" r:id="r{index}"/>'
                for index, name in enumerate(SHEETS if not missing_sheet else SHEETS[:-1])
            )
            workbook.writestr("xl/workbook.xml",
                             f'<workbook xmlns="{namespace}" xmlns:r="{relations}"><sheets>{sheets}</sheets></workbook>')
            workbook.writestr("xl/_rels/workbook.xml.rels", "<Relationships>"+"".join(
                f'<Relationship Id="r{i}" Target="worksheets/sheet{i+1}.xml"/>'
                for i in range(3)
            )+"</Relationships>")
            for index in range(3):
                header = "".join(
                    f'<c r="{column}1" t="s"><v>{value}</v></c>'
                    for column, value in (("A", 3 if invalid_header else 0), ("B", 1), ("C", 2))
                )
                cells = ('<c r="A2" t="s"><v>3</v></c>'
                         f'<c r="B2" t="s">{"<f>1+1</f>" if formula else ""}<v>4</v></c>'
                         '<c r="C2" t="s"><v>5</v></c>')
                workbook.writestr(f"xl/worksheets/sheet{index+1}.xml",
                                  f'<worksheet xmlns="{namespace}"><sheetData><row>{header}</row>'
                                  f'<row>{cells}</row></sheetData></worksheet>')

    def test_workbook_uses_relationships_and_preserves_string_id_precision(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"ids.xlsx"
            self.write_workbook(path)
            rows = read_identity_rows(path)
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["root_id"], "720575940611160930")
            self.assertEqual(rows[1]["root_id"], "720575940628755815")
            self.assertEqual({row["worksheet"] for row in rows}, set(SHEETS))

    def test_unexpected_workbook_schema_fails_explicitly(self):
        for kwargs in ({"formula": True}, {"invalid_header": True}, {"missing_sheet": True}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)/"ids.xlsx"
                self.write_workbook(path, **kwargs)
                with self.assertRaises(ValueError):
                    read_identity_rows(path)
