"""Audit version-matched takeoff candidate IDs/chemical edges; not a flight controller."""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from datasets import CATALOG, ROOT
from run_flywire_sugar import verified_inputs


def population(row: dict) -> str | None:
    if row["cell_type"] == "DNp01" and row["hemibrain_type"] == "Giant Fiber":
        return "GF"
    for label in ("LC4", "LPLC2"):
        if row["cell_type"] == label or row["hemibrain_type"] == label:
            return label
    return None


def select_neurons(rows: list[dict], model_ids: set[str]) -> list[dict]:
    result = []
    seen = set()
    for row in rows:
        label = population(row)
        if label is None:
            continue
        root_id = row["root_id"]
        if not root_id.isdecimal() or root_id in seen:
            raise ValueError("Takeoff annotations contain invalid or duplicate candidate root IDs")
        seen.add(root_id)
        result.append({
            "root_id": root_id, "population": label,
            "cell_type": row["cell_type"], "hemibrain_type": row["hemibrain_type"],
            "side": row["side"], "annotation_status": row.get("status", ""),
            "in_model": root_id in model_ids,
        })
    if {row["population"] for row in result} != {"GF", "LC4", "LPLC2"}:
        raise ValueError("Required takeoff populations are absent; no substitute labels used")
    gf = [row for row in result if row["population"] == "GF"]
    if len(gf) != 2 or {row["side"] for row in gf} != {"left", "right"}:
        raise ValueError("Expected exactly one annotated giant fiber per side")
    return result


def run(data_dir: Path, output: Path):
    import numpy as np
    import pandas as pd

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in [data_dir, output]):
        raise ValueError("Biological inputs/derived audit outputs must be outside Git")
    if output.exists():
        raise FileExistsError("Choose a new audit output directory")
    catalog = json.loads(CATALOG.read_text())
    by_id = {entry["id"]: entry for entry in catalog["datasets"]}
    annotations = verified_inputs(data_dir, by_id["flywire-annotations-630-v1.1.0"])
    model = verified_inputs(data_dir, by_id["flywire-model-630"])
    annotation_path = annotations["Supplemental_file1_annotations.tsv"]
    with annotation_path.open() as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"root_id", "cell_type", "hemibrain_type", "side"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Pinned annotation schema lacks required identity fields")
        rows = list(reader)
    ids = pd.read_csv(model["2023_03_23_completeness_630_final.csv"], index_col=0).index
    if len(ids) != 127400 or not ids.is_unique:
        raise ValueError("Model neuron identity/count mismatch")
    selected = select_neurons(rows, {str(value) for value in ids})
    edges = pd.read_parquet(model["2023_03_23_connectivity_630_final.parquet"])
    if len(edges) != 14687178:
        raise ValueError("Model edge count mismatch")
    for side in ("Presynaptic", "Postsynaptic"):
        indices = edges[f"{side}_Index"].to_numpy()
        if indices.dtype.kind not in "iu" or indices.min() < 0 or indices.max() >= len(ids):
            raise ValueError("Invalid model edge indices")
        if not np.array_equal(ids.to_numpy()[indices], edges[f"{side}_ID"].to_numpy()):
            raise ValueError("Model edge IDs and indices disagree")
    candidates = {int(row["root_id"]): row for row in selected if row["in_model"]}
    gf_ids = {key for key, row in candidates.items() if row["population"] == "GF"}
    input_ids = {key for key, row in candidates.items() if row["population"] in {"LC4", "LPLC2"}}
    direct = edges[
        edges.Presynaptic_ID.isin(input_ids) & edges.Postsynaptic_ID.isin(gf_ids)
    ]
    direct_records = []
    for row in direct.to_dict("records"):
        direct_records.append({
            "source_id": str(row["Presynaptic_ID"]), "target_id": str(row["Postsynaptic_ID"]),
            "population": candidates[row["Presynaptic_ID"]]["population"],
            "source_side": candidates[row["Presynaptic_ID"]]["side"],
            "target_side": candidates[row["Postsynaptic_ID"]]["side"],
            "contacts": int(row["Connectivity"]), "model_sign": int(row["Excitatory"]),
            "signed_contact_weight": int(row["Excitatory x Connectivity"]),
        })
    groups = []
    for label in ["LC4", "LPLC2"]:
        for target in sorted(gf_ids):
            matched = [row for row in direct_records if row["population"] == label and row["target_id"] == str(target)]
            groups.append({
                "population": label, "gf_id": str(target),
                "gf_side": candidates[target]["side"],
                "direct_source_neurons": len({row["source_id"] for row in matched}),
                "summed_chemical_contacts": sum(row["contacts"] for row in matched),
                "sign_counts": dict(Counter(str(row["model_sign"]) for row in matched)),
            })
    missing = [row["root_id"] for row in selected if not row["in_model"]]
    incoming = {
        str(target): int(edges.loc[edges.Postsynaptic_ID == target, "Connectivity"].sum())
        for target in gf_ids
    }
    output.mkdir(parents=True)
    report = {
        "status": "candidate_audit_completed",
        "annotation_dataset": "flywire-annotations-630-v1.1.0",
        "model_dataset": "flywire-model-630", "materialization": 630,
        "annotation_sha256": hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "populations": dict(Counter(row["population"] for row in selected)),
        "missing_model_ids": missing,
        "giant_fibers": [row for row in selected if row["population"] == "GF"],
        "direct_input_groups": groups,
        "total_gf_incoming_model_contacts": incoming,
        "candidate_neurons": selected,
        "direct_chemical_edges": direct_records,
        "takeoff_ready": False,
        "limitations": [
            "Historical annotations and direct chemical edges verified; population response encoding not validated.",
            "Chemical graph omits required electrical/VNC/muscle pathways.",
            "No automatic body takeoff, GF threshold rule, or sustained flight decoder implemented.",
            "Annotation outlier status retained; model sign is a processed assumption, not measured synaptic efficacy.",
        ],
    }
    (output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in [
        "status", "populations", "missing_model_ids", "giant_fibers", "direct_input_groups", "takeoff_ready",
    ]}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir)
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"ERROR: takeoff audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
