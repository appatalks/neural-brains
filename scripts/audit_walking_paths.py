"""Audit pinned walking/halting identities and chemical inputs; no motor wiring."""

import argparse
import csv
import json
import posixpath
import re
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from datasets import CATALOG, ROOT
from fly_connections import ConnectionIndex, ensure_index
from run_flywire_sugar import PROTOCOL, verified_inputs


SHEETS = ("stop", "walk", "walk_outputs")
CORE_NAMES = {"P9", "FG", "BB", "P9-oDN1", "BPN_SEZ_DN2", "DNa02"}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_workbook_sheets(path, requested):
    """Read published XLSX values without float conversion of root IDs."""
    result = {}
    with ZipFile(path) as workbook:
        strings = [
            "".join(node.itertext())
            for node in ET.fromstring(workbook.read("xl/sharedStrings.xml")).findall("s:si", NS)
        ]
        targets = {
            node.attrib["Id"]: posixpath.normpath(posixpath.join("xl", node.attrib["Target"]))
            for node in ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        }
        sheets = {
            node.attrib["name"]: targets[node.attrib[REL]]
            for node in ET.fromstring(workbook.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS)
        }
        for sheet in requested:
            if sheet not in sheets:
                raise ValueError(f"Missing published identity worksheet: {sheet}")
            populated = []
            for row in ET.fromstring(workbook.read(sheets[sheet])).findall(".//s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    value = cell.find("s:v", NS)
                    if value is None or value.text is None:
                        continue
                    if cell.find("s:f", NS) is not None:
                        raise ValueError("Identity workbook contains an unexpected formula")
                    column = re.sub(r"\d+$", "", cell.attrib["r"])
                    cells[column] = strings[int(value.text)] if cell.get("t") == "s" else value.text
                if cells:
                    populated.append(cells)
            result[sheet] = populated
    return result


def read_identity_rows(path):
    rows = []
    for sheet, populated in read_workbook_sheets(path, SHEETS).items():
        if not populated or any(
            populated[0].get(column) != expected
            for column, expected in (("A", "Name"), ("B", "ID_left"), ("C", "ID_right"))
        ):
            raise ValueError(f"Unexpected published identity columns in {sheet}")
        for cells in populated[1:]:
            if not cells.get("A"):
                raise ValueError(f"Identity row lacks a name in {sheet}")
            for column, side in (("B", "left"), ("C", "right")):
                if cells.get(column):
                    rows.append({
                        "name": cells["A"], "root_id": cells[column].strip(),
                        "workbook_side": side, "worksheet": sheet,
                        "comment": cells.get("D", ""),
                    })
    return rows


def primary_populations(path, annotations, model_ids):
    sheets = read_workbook_sheets(path, ("FlyWire", "FANC+MANC"))
    expected_headers = {
        "FlyWire": {"A": "ID_left", "B": "ID_right", "E": "Name in this study"},
        "FANC+MANC": {"A": "FANC_ID_left", "B": "FANC_ID_right", "C": "MANC_ID_left",
                      "D": "MANC_ID_right", "F": "Name in this study"},
    }
    for sheet, headers in expected_headers.items():
        if not sheets[sheet] or any(sheets[sheet][0].get(key) != value for key, value in headers.items()):
            raise ValueError(f"Unexpected primary identity columns in {sheet}")
    populations = {name: [] for name in ("P9", "BPN", "FG", "BB", "BDN2", "oDN1", "BRK")}
    seen = set()
    for row in sheets["FlyWire"][1:]:
        name = row.get("E", "").strip()
        population = "BRK" if name in {"BRK1, BRK2", "BRK3, BRK4", "BRK5, BRK6"} else name
        if population not in populations:
            continue
        if population == "BPN" and (
            not row.get("C", "").startswith("Type 1 BPN") or row.get("D", "").strip() != "CL210"
        ):
            continue
        for column, side in (("A", "left"), ("B", "right")):
            root_id = row.get(column, "").strip()
            if not root_id.isascii() or not root_id.isdecimal() or root_id in seen:
                raise ValueError("Primary walking identities are invalid or duplicated")
            if root_id not in model_ids or root_id not in annotations:
                raise ValueError(f"Primary walking ID {root_id} is absent from the preserved model or annotations")
            annotation = annotations[root_id]
            if annotation["side"] != side:
                raise ValueError(f"Primary walking laterality differs from annotation for {root_id}")
            seen.add(root_id)
            populations[population].append({
                "root_id": root_id, "side": side, "population": population,
                "primary_name": name, "primary_cell_type": row.get("D", "").strip(),
                "cell_type": annotation["cell_type"], "hemibrain_type": annotation["hemibrain_type"],
                "predicted_nt": annotation["top_nt"], "in_model": True,
            })
    for name, rows in populations.items():
        required = 12 if name == "BPN" else 6 if name == "BRK" else 2
        if len(rows) != required or sum(row["side"] == "left" for row in rows) != required//2:
            raise ValueError(f"Unexpected primary population count for {name}")
    return populations, sheets["FANC+MANC"][1:]


def select_candidates(rows, annotations, model_ids):
    selected = []
    seen = set()
    for row in rows:
        if row["name"] not in CORE_NAMES and not re.fullmatch(r"BPN_1[a-f]", row["name"]):
            continue
        root_id = row["root_id"]
        if not root_id.isascii() or not root_id.isdecimal() or root_id in seen:
            raise ValueError("Invalid, rounded or duplicate walking candidate root ID")
        seen.add(root_id)
        annotation = annotations.get(root_id)
        annotation_side = annotation["side"] if annotation else None
        selected.append({
            **row, "in_model": root_id in model_ids,
            "annotation_present": annotation is not None,
            "annotation_side": annotation_side,
            "side_conflict": annotation_side in {"left", "right"} and annotation_side != row["workbook_side"],
            "cell_type": annotation["cell_type"] if annotation else None,
            "hemibrain_type": annotation["hemibrain_type"] if annotation else None,
            "predicted_nt": annotation["top_nt"] if annotation else None,
            "paper_alias_unresolved": row["name"] == "BPN_SEZ_DN2",
        })
    expected = CORE_NAMES | {f"BPN_1{letter}" for letter in "abcdef"}
    if {row["name"] for row in selected} != expected:
        raise ValueError("Required walking/halting workbook names are missing")
    for name in expected:
        group = [row for row in selected if row["name"] == name]
        if len(group) != 2 or {row["workbook_side"] for row in group} != {"left", "right"}:
            raise ValueError(f"Expected one workbook ID per source-assigned side for {name}")
    return selected


def run(data_dir, output):
    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose verified external inputs and a new external audit directory")
    datasets = {entry["id"]: entry for entry in json.loads(CATALOG.read_text())["datasets"]}
    workbook = verified_inputs(data_dir, datasets["walking-halting-ids-630-v1.0.0"])
    annotations = verified_inputs(data_dir, datasets["flywire-annotations-630-v1.1.0"])
    model = verified_inputs(data_dir, datasets["flywire-model-630"])
    primary = verified_inputs(data_dir, datasets["walking-halting-primary-identities-2024"])
    with annotations["Supplemental_file1_annotations.tsv"].open() as stream:
        annotation_by_id = {row["root_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
    with model["2023_03_23_completeness_630_final.csv"].open() as stream:
        reader = csv.reader(stream)
        next(reader)
        ids = [row[0] for row in reader]
    if len(ids) != 127400 or len(set(ids)) != len(ids):
        raise ValueError("Walking audit requires the preserved 127400-neuron model")
    candidates = select_candidates(read_identity_rows(workbook["flywire_ids_630.xlsx"]), annotation_by_id, set(ids))
    populations, vnc_matches = primary_populations(
        primary["41586_2024_7854_MOESM4_ESM.xlsx"], annotation_by_id, set(ids))
    primary_by_id = {row["root_id"]: row for rows in populations.values() for row in rows}
    for candidate in candidates:
        resolved = primary_by_id.get(candidate["root_id"])
        if resolved is not None:
            candidate["primary_side"] = resolved["side"]
            candidate["primary_population"] = resolved["population"]
            candidate["primary_agrees_with_annotation"] = resolved["side"] == candidate["annotation_side"]
            candidate["paper_alias_unresolved"] = False
    commit = json.loads(PROTOCOL.read_text())["upstream_commit"]
    index_dir = ensure_index(data_dir, model["2023_03_23_connectivity_630_final.parquet"], ids, commit)
    index = ConnectionIndex(index_dir, ids, commit)
    selected_ids = {row["root_id"] for row in candidates}
    for candidate in candidates:
        if not candidate["in_model"]:
            candidate["chemical_inputs_status"] = "absent_from_preserved_model"
            continue
        first = index.lookup(candidate["root_id"], "incoming", limit=100)
        edges = list(first["edges"])
        for offset in range(100, first["total"], 100):
            edges.extend(index.lookup(candidate["root_id"], "incoming", offset, 100)["edges"])
        groups = defaultdict(lambda: {"neurons": 0, "contacts": 0})
        for edge in edges:
            annotation = annotation_by_id.get(edge["source_id"])
            label = (annotation["cell_type"] or annotation["hemibrain_type"]) if annotation else ""
            group = groups[label or "unannotated"]
            group["neurons"] += 1
            group["contacts"] += edge["contacts"]
        candidate["incoming_neurons"] = first["total"]
        candidate["incoming_contacts"] = sum(edge["contacts"] for edge in edges)
        candidate["selected_path_inputs"] = [edge for edge in edges if edge["source_id"] in selected_ids]
        candidate["top_input_types"] = [
            {"type": label, **counts}
            for label, counts in sorted(groups.items(), key=lambda item: (-item[1]["contacts"], item[0]))[:12]
        ]
    report = {
        "schema_version": 1, "reviewed_on": "2026-10-11",
        "annotation_version": "v1.1.0 / FlyWire630", "upstream_model_commit": commit,
        "workbook_version": datasets["walking-halting-ids-630-v1.0.0"]["version"],
        "candidates": candidates, "candidate_count": len(candidates),
        "matched_model": sum(row["in_model"] for row in candidates),
        "side_conflicts": sum(row["side_conflict"] for row in candidates),
        "missing_model_ids": [row["root_id"] for row in candidates if not row["in_model"]],
        "primary_populations": populations, "primary_vnc_correspondence_rows": vnc_matches,
        "identity_resolution": "Primary Supplementary Table 3 confirms aliases and agrees with historical annotation sides; old code workbook sides remain conflicting.",
        "motor_controller_modified": False, "neural_stimulation_performed": False,
        "limitations": [
            "Workbook and annotation side labels are preserved separately; conflicts are not silently corrected.",
            "BDN2 and Brake IDs are confirmed by primary table, not by near-name inference.",
            "Primary VNC correspondence rows retain separate female FANC and male MANC namespaces.",
            "BPN selection is the 12 CL210 Type1 IDs only; other BPN classes and one conflicting Type1/SMP461 row are excluded, not relabeled.",
            "Brain-side chemical inputs only; VNC, proprioception and muscle dynamics remain missing.",
            "Assigned signed contacts are proxies, not conductances or calibrated force laws.",
            "Published walking model connectivity differs in byte size; no replacement or spike parity claimed.",
        ],
    }
    output.mkdir(parents=True)
    (output/"audit.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.data_dir, args.output_dir)
    print(json.dumps({key: value for key, value in report.items() if key != "candidates"}, indent=2))
