"""Artificial visual-population activation diagnostic; no looming or body takeoff."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from audit_takeoff_circuit import run as audit
from datasets import CATALOG, ROOT
from run_flywire_sugar import verified_inputs


def run(data_dir: Path, output: Path):
    import numpy as np
    import pandas as pd
    from brian2 import Hz, ms, seed, start_scope

    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        raise ValueError("Choose a new external probe output directory")
    output.mkdir(parents=True)
    (output / "status.json").write_text('{"status": "running"}\n')
    try:
        report = audit(data_dir, output / "identity-audit")
        if report["missing_model_ids"]:
            raise ValueError("Cannot stimulate unverified or absent model neurons")
        dataset = next(d for d in json.loads(CATALOG.read_text())["datasets"] if d["id"] == "flywire-model-630")
        paths = verified_inputs(data_dir, dataset)
        comp = paths["2023_03_23_completeness_630_final.csv"]
        con = paths["2023_03_23_connectivity_630_final.parquet"]
        mapping = {str(value): index for index, value in enumerate(pd.read_csv(comp, index_col=0).index)}
        spec = importlib.util.spec_from_file_location("takeoff_probe_model", paths["model.py"])
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        cases = []
        for label in ["none", "LC4", "LPLC2", "both"]:
            neurons = [row for row in report["candidate_neurons"] if row["population"] in (
                {"LC4", "LPLC2"} if label == "both" else {label}
            )]
            start_scope()
            seed(420)
            params = dict(model.default_params, r_poi=100 * Hz, t_run=1000 * ms, n_run=1)
            spikes = model.run_trial(
                [mapping[row["root_id"]] for row in neurons], [], [], comp, con, params
            )
            readouts = {}
            for gf in report["giant_fibers"]:
                times = np.asarray(spikes.get(mapping[gf["root_id"]], []) / ms).tolist() if mapping[gf["root_id"]] in spikes else []
                readouts[gf["root_id"]] = {
                    "side": gf["side"], "spike_count": len(times), "spike_times_ms": times,
                }
            result = {
                "artificially_activated_population": label, "input_count": len(neurons),
                "input_ids": [row["root_id"] for row in neurons], "seed": 420,
                "activation_Hz": 100, "duration_ms": 1000,
                "network_spikes": sum(len(times) for times in spikes.values()),
                "giant_fiber_readouts": readouts,
            }
            cases.append(result)
            print(json.dumps({k: v for k, v in result.items() if k != "input_ids"}), flush=True)
        if cases[0]["network_spikes"] != 0:
            raise ValueError("Resting control unexpectedly spikes")
        summary = {
            "status": "diagnostic_completed", "cases": cases,
            "upstream_commit": "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960",
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": "Artificial synchronous-rate population activation in existing LIF brain. Not calibrated visual/looming input, intervention validation, or motor/flight output.",
            "takeoff_ready": False,
        }
        (output / "probe.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "status.json").write_text('{"status": "diagnostic_completed"}\n')
        return summary
    except Exception as error:
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": str(error)}) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir)
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as error:
        print(f"ERROR: takeoff circuit probe failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
