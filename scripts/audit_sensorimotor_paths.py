"""Version-matched steering/landing candidate inputs; no invented motor decoder."""

import argparse
import csv
import json
import hashlib
from collections import defaultdict
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_connections import ConnectionIndex, ensure_index
from run_flywire_sugar import PROTOCOL, verified_inputs


CANDIDATE_TYPES = ("DNa04", "DNa05", "DNp07", "DNp10")
MANC_MATCHING_SHA256 = "e559a0e6759044c6a969dab53c56a843e3c1d8d957fbb3881b78488774dfb687"


def select_manc_matches(rows):
    matches = []
    seen = set()
    for row in rows:
        if row["type"] not in CANDIDATE_TYPES:
            continue
        body_id = row["bodyid"]
        if not body_id.isascii() or not body_id.isdecimal() or body_id in seen:
            raise ValueError("Primary MANC table has invalid or duplicate body IDs")
        seen.add(body_id)
        if row["side"] not in {"L", "R"} or row["confidence_1_5"] not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Primary MANC table lacks explicit side/matching confidence")
        matches.append({
            "manc_body_id": body_id, "manc_group": row["group"],
            "type": row["type"], "systematic_type": row["systematic_type"],
            "side": {"L": "left", "R": "right"}[row["side"]],
            "published_matching_confidence_1_5": int(row["confidence_1_5"]),
            "scope": "Primary male VNC light-level type match; not female FlyWire root identity or a conductance/physiology measurement.",
        })
    for population in CANDIDATE_TYPES:
        group = [row for row in matches if row["type"] == population]
        if len(group) != 2 or {row["side"] for row in group} != {"left", "right"}:
            raise ValueError(f"Expected one published MANC {population} body per side")
    return matches


def select_candidates(rows, model_ids):
    candidates = []
    seen = set()
    for row in rows:
        labels = {row["cell_type"], row["hemibrain_type"]} & set(CANDIDATE_TYPES)
        if not labels:
            continue
        if len(labels) != 1:
            raise ValueError("Conflicting steering/landing type annotations")
        root_id = row["root_id"]
        if not root_id.isascii() or not root_id.isdecimal() or root_id in seen:
            raise ValueError("Invalid or duplicate steering/landing identity")
        seen.add(root_id)
        label = labels.pop()
        if row["side"] not in {"left", "right"}:
            raise ValueError("Candidate requires an explicit bilateral side")
        candidates.append({
            "root_id": root_id, "population": label, "side": row["side"],
            "cell_type": row["cell_type"], "hemibrain_type": row["hemibrain_type"],
            "matched_field": "cell_type" if row["cell_type"] == label else "hemibrain_type",
            "in_model": root_id in model_ids,
            "evidence_scope": "candidate steering anatomy" if label.startswith("DNa")
            else "causal landing leg-extension response; not complete touchdown",
        })
    for label in CANDIDATE_TYPES:
        group = [r for r in candidates if r["population"] == label]
        if {r["side"] for r in group} != {"left", "right"} or (label.startswith("DNp") and len(group) != 2):
            raise ValueError(f"Missing or ambiguous bilateral landing/steering annotations for {label}")
        for row in group:
            row["ambiguous_type_correspondence"] = len(group) != 2
    return candidates


def run(data_dir, output, manc_matching=None):
    import pandas as pd

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(p == ROOT or ROOT in p.parents for p in [data_dir, output]) or output.exists():
        raise ValueError("Choose verified external inputs and a new external audit directory")
    by_id = {d["id"]: d for d in json.loads(CATALOG.read_text())["datasets"]}
    annotations = verified_inputs(data_dir, by_id["flywire-annotations-630-v1.1.0"])
    model = verified_inputs(data_dir, by_id["flywire-model-630"])
    with annotations["Supplemental_file1_annotations.tsv"].open() as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    ids = pd.read_csv(model["2023_03_23_completeness_630_final.csv"], index_col=0).index
    if len(ids) != 127400 or not ids.is_unique:
        raise ValueError("Sensorimotor audit requires the verified full model")
    ids = list(ids.astype(str))
    candidates = select_candidates(rows, set(ids))
    if any(not r["in_model"] for r in candidates):
        raise ValueError("Candidate neuron absent from the model; no substitute permitted")
    annotation_by_id = {r["root_id"]: r for r in rows}
    commit = json.loads(PROTOCOL.read_text())["upstream_commit"]
    index_dir = ensure_index(data_dir, model["2023_03_23_connectivity_630_final.parquet"], ids, commit)
    index = ConnectionIndex(index_dir, ids, commit)
    for candidate in candidates:
        edges = []
        first = index.lookup(candidate["root_id"], "incoming", limit=100)
        edges.extend(first["edges"])
        for offset in range(100, first["total"], 100):
            edges.extend(index.lookup(candidate["root_id"], "incoming", offset, 100)["edges"])
        groups = defaultdict(lambda: {"neurons": 0, "contacts": 0, "signed_contact_proxy": 0})
        for edge in edges:
            annotation = annotation_by_id.get(edge["source_id"])
            label = (annotation["cell_type"] or annotation["hemibrain_type"]) if annotation else ""
            group = groups[label or "unannotated"]
            group["neurons"] += 1
            group["contacts"] += edge["contacts"]
            group["signed_contact_proxy"] += edge["signed_contacts"]
        candidate["incoming_neurons"] = first["total"]
        candidate["incoming_contacts"] = sum(e["contacts"] for e in edges)
        candidate["top_input_types"] = [
            {"type": label, **values} for label, values in
            sorted(groups.items(), key=lambda item: (-item[1]["contacts"], item[0]))[:15]
        ]
        candidate["top_input_neurons"] = sorted(edges, key=lambda e: (-e["contacts"], e["source_id"]))[:25]
    report = {
        "schema_version": 1, "upstream_commit": commit, "annotation_version": "v1.1.0 / FlyWire630",
        "candidates": candidates, "motor_controller_modified": False,
        "sources": {
            "landing": "https://doi.org/10.1038/s41593-019-0413-4",
            "steering_anatomy": "https://doi.org/10.7554/eLife.96084",
        },
        "limitations": [
            "Brain-side chemical contacts only; no VNC/neuromuscular dynamics in this model.",
            "MANC motor anatomy is a separate male specimen; root IDs cannot be joined to female FlyWire IDs.",
            "Contact counts and assigned signs are not conductances or calibrated physiological transfer functions.",
            "Landing leg extension is not complete braking, touchdown and walking re-entry.",
            "No neural input stimulation, electrical conductance, actuator gain or motor decoder was invented.",
        ],
    }
    if manc_matching is not None:
        content = manc_matching.read_bytes()
        if hashlib.sha256(content).hexdigest() != MANC_MATCHING_SHA256:
            raise ValueError("Primary MANC matching table differs from the inspected publisher v2 asset")
        # Publisher CSV author names contain Windows-1252 characters.
        import io
        matches = select_manc_matches(csv.DictReader(io.StringIO(content.decode("cp1252"))))
        report["manc_matching"] = {
            "source_url": "https://cdn.elifesciences.org/articles/96084/elife-96084-supp1-v2.csv",
            "file_sha256": hashlib.sha256(content).hexdigest(),
            "text_encoding": "cp1252", "matches": matches,
            "flywire_correspondence": "Name-level only. Conflicting FlyWire annotation pairs remain unresolved and are not merged.",
        }
    output.mkdir(parents=True)
    (output/"audit.json").write_text(json.dumps(report, indent=2)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manc-matching", type=Path, help="Downloaded primary eLife DN matching CSV; no automatic cross-specimen identity join")
    args = parser.parse_args()
    try:
        report = run(args.data_dir, args.output_dir, args.manc_matching)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"ERROR: sensorimotor audit failed: {error}\n")
    print(json.dumps([
        {k: c[k] for k in ["population", "side", "in_model", "incoming_neurons", "incoming_contacts"]}
        for c in report["candidates"]
    ], indent=2))


if __name__ == "__main__":
    main()
