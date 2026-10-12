"""Read-only touch/internal-state identity and chemical-path audit; no stimulation."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from audit_walking_paths import read_workbook_sheets
from datasets import CATALOG, ROOT
from fly_connections import ConnectionIndex, ensure_index
from run_flywire_sugar import PROTOCOL, verified_inputs


MDN_PRIMARY_NAMES = {"MDN1, MDN2", "MDN3, MDN4"}


def select_targets(rows, model_ids, primary_rows):
    annotation_by_id = {row["root_id"]: row for row in rows}
    targets = []
    for primary in primary_rows:
        if primary.get("E") not in MDN_PRIMARY_NAMES:
            continue
        for column, side in (("A", "left"), ("B", "right")):
            value = primary.get(column, "").strip()
            annotation = annotation_by_id.get(value)
            if (not value.isascii() or not value.isdecimal() or value not in model_ids
                    or annotation is None or annotation["side"] != side
                    or annotation["hemibrain_type"] != "MDN"):
                raise ValueError("Primary MDN identity/laterality does not match the pinned model")
            targets.append({
                "root_id": value, "population": "MDN", "side": side,
                "primary_name": primary["E"], "primary_cell_type": primary.get("D", "").strip(),
                "cell_type": annotation["cell_type"], "hemibrain_type": annotation["hemibrain_type"],
                "predicted_nt": annotation["top_nt"], "in_model": True,
                "scope": "Adult backward-walking output identity; not a complete touch/recovery controller",
            })
    if len(targets) != 4 or len({row["root_id"] for row in targets}) != 4:
        raise ValueError("Expected four exact primary MDN cells")
    for row in rows:
        if "OA-VPM4" not in {row["cell_type"], row["hemibrain_type"]}:
            continue
        if (row["root_id"] not in model_ids or row["side"] not in {"left", "right"}
                or row["super_class"] != "central" or row["top_nt"] != "octopamine"):
            raise ValueError("OA-VPM4 candidate annotation/model identity is unresolved")
        targets.append({
            "root_id": row["root_id"], "population": "OA-VPM4", "side": row["side"],
            "cell_type": row["cell_type"], "hemibrain_type": row["hemibrain_type"],
            "predicted_nt": row["top_nt"], "predicted_nt_confidence": row["top_nt_conf"],
            "in_model": True,
            "scope": "Exact annotated candidate; primary causal evidence is feeding initiation, not general arousal/takeoff",
        })
    oa = [row for row in targets if row["population"] == "OA-VPM4"]
    if len(oa) != 2 or {row["side"] for row in oa} != {"left", "right"}:
        raise ValueError("Expected an explicit bilateral OA-VPM4 annotation pair")
    if len({row["root_id"] for row in targets}) != len(targets):
        raise ValueError("Touch/state targets contain duplicated identities")
    return targets


def inventory(rows, model_ids):
    categories = {
        "ascending": lambda row: row["super_class"] == "ascending",
        "head_bristle": lambda row: row["cell_class"] == "mechanosensory" and row["cell_sub_class"] == "head bristle",
        "eye_bristle": lambda row: row["cell_class"] == "mechanosensory" and row["cell_sub_class"] == "eye bristle",
        "predicted_octopamine": lambda row: row["top_nt"] == "octopamine",
        "named_OA": lambda row: row["cell_type"].startswith("OA-") or row["hemibrain_type"].startswith("OA-"),
    }
    result = {}
    for name, predicate in categories.items():
        selected = [row for row in rows if predicate(row)]
        result[name] = {
            "annotation_rows": len(selected),
            "matched_model": sum(row["root_id"] in model_ids for row in selected),
            "named_annotation_rows": sum(bool(row["cell_type"] or row["hemibrain_type"]) for row in selected),
            "non_neuron_annotation_rows": sum(row["super_class"] == "not_a_neuron" for row in selected),
        }
    result["exact_label_matches"] = {
        name: [row["root_id"] for row in rows
               if name in {row["cell_type"], row["hemibrain_type"]}]
        for name in ("TLA", "TwoLumps", "FeCO", "NOMPC", "Tdc2", "Tbh")
    }
    return result


def run(data_dir, output):
    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose verified external data and a new external research audit")
    datasets = {entry["id"]: entry for entry in json.loads(CATALOG.read_text())["datasets"]}
    annotation = verified_inputs(data_dir, datasets["flywire-annotations-630-v1.1.0"])
    model = verified_inputs(data_dir, datasets["flywire-model-630"])
    primary = verified_inputs(data_dir, datasets["walking-halting-primary-identities-2024"])
    workbook = verified_inputs(data_dir, datasets["walking-halting-ids-630-v1.0.0"])
    with annotation["Supplemental_file1_annotations.tsv"].open() as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    with model["2023_03_23_completeness_630_final.csv"].open() as stream:
        reader = csv.reader(stream)
        next(reader)
        ids = [row[0] for row in reader]
    if len(ids) != 127400 or len(set(ids)) != len(ids):
        raise ValueError("Touch/state audit requires the preserved full model ordering")
    primary_sheets = read_workbook_sheets(primary["41586_2024_7854_MOESM4_ESM.xlsx"], ("FlyWire", "FANC+MANC"))
    targets = select_targets(rows, set(ids), primary_sheets["FlyWire"][1:])
    annotation_by_id = {row["root_id"]: row for row in rows}
    commit = json.loads(PROTOCOL.read_text())["upstream_commit"]
    directory = ensure_index(data_dir, model["2023_03_23_connectivity_630_final.parquet"], ids, commit)
    index = ConnectionIndex(directory, ids, commit)
    for target in targets:
        first = index.lookup(target["root_id"], "incoming", limit=100)
        edges = list(first["edges"])
        for offset in range(100, first["total"], 100):
            edges.extend(index.lookup(target["root_id"], "incoming", offset, 100)["edges"])
        groups = defaultdict(lambda: {"neurons": 0, "contacts": 0, "signed_contact_proxy": 0})
        ascending = []
        mechanosensory = []
        for edge in edges:
            row = annotation_by_id.get(edge["source_id"])
            label = (row["cell_type"] or row["hemibrain_type"]) if row else ""
            group = groups[label or "unannotated"]
            group["neurons"] += 1
            group["contacts"] += edge["contacts"]
            group["signed_contact_proxy"] += edge["signed_contacts"]
            if row and row["super_class"] == "ascending":
                ascending.append({**edge, "cell_type": row["cell_type"], "hemibrain_type": row["hemibrain_type"],
                                  "side": row["side"], "predicted_nt": row["top_nt"],
                                  "identity_scope": "Ascending classification does not establish TwoLumps or touch encoding"})
            if row and row["cell_class"] == "mechanosensory":
                mechanosensory.append({**edge, "cell_sub_class": row["cell_sub_class"],
                                      "cell_type": row["cell_type"], "hemibrain_type": row["hemibrain_type"]})
        target["incoming_neurons"] = first["total"]
        target["incoming_contacts"] = sum(edge["contacts"] for edge in edges)
        target["ascending_inputs"] = ascending
        target["mechanosensory_inputs"] = mechanosensory
        target["top_input_types"] = [
            {"type": name, **values}
            for name, values in sorted(groups.items(), key=lambda item: (-item[1]["contacts"], item[0]))[:12]
        ]
    old = read_workbook_sheets(workbook["flywire_ids_630.xlsx"], ("walk",))["walk"]
    old_sides = {
        row[column]: side for row in old if row.get("A") in {"MDN_a", "MDN_b"}
        for column, side in (("B", "left"), ("C", "right")) if row.get(column)
    }
    for target in targets:
        if target["population"] == "MDN":
            target["old_code_workbook_side"] = old_sides.get(target["root_id"])
            target["old_code_side_conflict"] = target["old_code_workbook_side"] != target["side"]
    report = {
        "schema_version": 1, "reviewed_on": "2026-10-11", "annotation_version": "v1.1.0 / FlyWire630",
        "model_commit": commit, "targets": targets, "inventory": inventory(rows, set(ids)),
        "primary_MDN_vnc_rows": [row for row in primary_sheets["FANC+MANC"][1:] if row.get("F") == "MDN"],
        "stimulated_neurons": [], "motor_controller_modified": False,
        "signed_contact_scope": "Original processed snapshot weights, separate from historical annotation NT predictions; no physiological sign/conductance inferred or signs recalculated.",
        "limitations": [
            "No exact TLA/TwoLumps, FeCO, NOMPC, Tdc2 or Tbh label is substituted from near names.",
            "Head/eye bristles do not establish thorax/leg tactile encoding or peripheral force-to-spike laws.",
            "Generic ascending inputs are not confirmed touch or behavioral-state cell identities.",
            "OA-VPM4 causal evidence supports feeding, not spontaneous walking/flight.",
            "Predicted octopamine includes non-neuron/other-class rows; do not stimulate all predicted labels.",
            "Homogeneous fast chemical LIF signs do not implement octopamine GPCR/state-dependent modulation or metabolism.",
            "No current live app input, object placement, reset, fall response or behavior changed.",
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
    result = run(args.data_dir, args.output_dir)
    print(json.dumps({"targets": len(result["targets"]), "inventory": result["inventory"],
                      "motor_controller_modified": False}, indent=2))
