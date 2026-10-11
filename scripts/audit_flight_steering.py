"""Audit explicitly annotated DNg02 subtypes; not a neural steering decoder."""

import argparse
import csv
import json
import re
from pathlib import Path

from datasets import CATALOG, ROOT
from run_flywire_sugar import verified_inputs


def select_dng02(rows, model_ids):
    selected = []
    seen = set()
    for row in rows:
        label = row["cell_type"]
        if not re.fullmatch(r"DNg02(?:_[a-z]+)?", label):
            continue
        root_id = row["root_id"]
        if not root_id.isascii() or not root_id.isdecimal() or root_id in seen:
            raise ValueError("DNg02 annotations contain invalid or duplicate identities")
        if row["side"] not in {"left", "right"}:
            raise ValueError("DNg02 annotation lacks an explicit bilateral side")
        seen.add(root_id)
        selected.append({
            "root_id": root_id, "cell_type": label, "side": row["side"],
            "hemibrain_type": row["hemibrain_type"], "in_model": root_id in model_ids,
        })
    if not selected:
        raise ValueError("No explicitly annotated DNg02 candidates; no substitute types selected")
    return selected


def run(data_dir, output):
    import pandas as pd

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(p == ROOT or ROOT in p.parents for p in [data_dir, output]) or output.exists():
        raise ValueError("Choose external inputs and a new external audit output directory")
    by_id = {d["id"]: d for d in json.loads(CATALOG.read_text())["datasets"]}
    annotations = verified_inputs(data_dir, by_id["flywire-annotations-630-v1.1.0"])
    model = verified_inputs(data_dir, by_id["flywire-model-630"])
    ids = pd.read_csv(model["2023_03_23_completeness_630_final.csv"], index_col=0).index
    if len(ids) != 127400 or not ids.is_unique:
        raise ValueError("Flight-steering audit requires the verified 127400-neuron model")
    with annotations["Supplemental_file1_annotations.tsv"].open() as stream:
        selected = select_dng02(csv.DictReader(stream, delimiter="\t"), set(ids.astype(str)))
    report = {
        "annotation_version": "v1.1.0 / FlyWire630", "neurons": selected,
        "count": len(selected), "matched_model": sum(r["in_model"] for r in selected),
        "subtypes": {label: sum(r["cell_type"] == label for r in selected)
                     for label in sorted({r["cell_type"] for r in selected})},
        "scope": "Version-matched identities only. Subtype functional equivalence, sensory encoding and VNC/motor decoding are not established.",
    }
    output.mkdir(parents=True)
    (output/"dng02.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.data_dir, args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "neurons"}, indent=2))
