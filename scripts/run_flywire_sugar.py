"""Run a pinned FlyWire-630 sugar-to-MN9 experiment on external data."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import resource
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from datasets import CATALOG, ROOT, component, select_asset


PROTOCOL = ROOT / "experiments" / "flywire-sugar" / "experiment.json"


def verified_inputs(data_dir: Path, dataset: dict) -> dict[str, Path]:
    paths = {}
    for entry in dataset["selected_assets"]:
        asset = select_asset(dataset, entry["filename"])
        path = data_dir / dataset["id"] / (asset.filename + ".download") / asset.filename
        if asset.size_bytes is None or asset.checksum is None:
            raise ValueError(f"Verified input requires upstream size and checksum: {asset.filename}")
        algorithm, expected = asset.checksum.split(":")
        digest = hashlib.new("sha1" if algorithm == "git-blob-sha1" else algorithm, usedforsecurity=False)
        if algorithm == "git-blob-sha1":
            digest.update(f"blob {asset.size_bytes}\0".encode())
        sha256 = hashlib.sha256()
        count = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                sha256.update(chunk)
                count += len(chunk)
        if count != asset.size_bytes or expected != digest.hexdigest():
            label = "Git blob" if algorithm == "git-blob-sha1" else algorithm
            raise ValueError(f"Pinned {label} verification failed: {asset.filename}")
        receipt = json.loads((path.parent / "receipt.json").read_text())
        if (
            receipt["sha256"] != sha256.hexdigest()
            or receipt["upstream_checksum"] != asset.checksum
            or receipt["dataset_id"] != dataset["id"]
            or receipt["source_url"] != asset.url
        ):
            raise ValueError(f"Provenance receipt mismatch: {asset.filename}")
        paths[asset.filename] = path
    return paths


def acceptance(readout_counts: list[int], control_spikes: int, expected_trials: int) -> dict:
    if not readout_counts or any(count < 0 for count in readout_counts):
        raise ValueError("Readout counts must contain nonnegative trial observations")
    if control_spikes < 0 or expected_trials < 1:
        raise ValueError("Control spike count and expected trial count are invalid")
    activated = sum(count > 0 for count in readout_counts)
    complete = len(readout_counts) == expected_trials
    passed = complete and activated == expected_trials and control_spikes == 0
    return {
        "completed_stimulated_trials": len(readout_counts),
        "required_stimulated_trials": expected_trials,
        "mn9_activated_trials": activated,
        "mn9_activation_fraction": activated / len(readout_counts),
        "control_spikes": control_spikes,
        "protocol_complete": complete,
        "passed": passed,
        "status": "passed" if passed else ("incomplete_smoke_test" if not complete else "failed"),
    }


def run(data_dir: Path, run_name: str, trials: int | None = None) -> Path:
    import numpy as np
    import pandas as pd
    from brian2 import Hz, Network, defaultclock, ms, prefs, seed, start_scope

    started = perf_counter()
    data_dir = data_dir.expanduser().resolve()
    component(run_name)
    if data_dir == ROOT or ROOT in data_dir.parents:
        raise ValueError("Data/results must remain outside the repository")
    protocol = json.loads(PROTOCOL.read_text())
    trials = protocol["trial_count"] if trials is None else trials
    if not 1 <= trials <= protocol["trial_count"]:
        raise ValueError("Trials must be between 1 and the protocol's full trial count")
    catalog = json.loads(CATALOG.read_text())
    matches = [d for d in catalog["datasets"] if d["id"] == protocol["dataset_id"]]
    if len(matches) != 1:
        raise ValueError("Expected exactly one pinned model dataset")
    dataset = matches[0]
    inputs = verified_inputs(data_dir, dataset)
    output = data_dir / "results" / protocol["id"] / run_name
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError("Resolved output must remain outside the repository")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite run directory: {output}")

    comp = inputs["2023_03_23_completeness_630_final.csv"]
    con = inputs["2023_03_23_connectivity_630_final.parquet"]
    neurons = pd.read_csv(comp, index_col=0)
    edges = pd.read_parquet(con)
    required = {
        "Presynaptic_ID", "Postsynaptic_ID", "Presynaptic_Index", "Postsynaptic_Index",
        "Connectivity", "Excitatory", "Excitatory x Connectivity",
    }
    if not required <= set(edges.columns):
        raise ValueError("Connectivity export does not have the pinned model schema")
    if not neurons.index.is_unique or neurons.index.dtype.kind not in "iu":
        raise ValueError("Neuron IDs must be unique exact integers")
    if len(neurons) != 127400 or len(edges) != 14687178:
        raise ValueError("Pinned snapshot neuron/connection counts disagree with inspected inputs")
    ids = neurons.index.to_numpy()
    for side in ("Presynaptic", "Postsynaptic"):
        indices = edges[f"{side}_Index"].to_numpy()
        if indices.dtype.kind not in "iu" or indices.min() < 0 or indices.max() >= len(ids):
            raise ValueError(f"Invalid {side} simulation indices")
        if not np.array_equal(ids[indices], edges[f"{side}_ID"].to_numpy()):
            raise ValueError(f"{side} ID/index mapping does not match completeness order")
    if (edges["Connectivity"] <= 0).any() or not edges["Excitatory"].isin([-1, 0, 1]).all():
        raise ValueError("Invalid contact counts or sign labels")
    if not np.array_equal(
        edges["Connectivity"] * edges["Excitatory"], edges["Excitatory x Connectivity"]
    ):
        raise ValueError("Processed signed weights disagree with their source columns")
    input_ids = [int(value) for value in protocol["input_ids"]]
    readout_id = int(protocol["readout_id"])
    if len(set(input_ids)) != len(input_ids) or not set(input_ids + [readout_id]) <= set(ids):
        raise ValueError("Stimulus/readout IDs are duplicate or absent from the pinned network")
    mapping = {int(value): index for index, value in enumerate(ids)}
    readout_index = mapping[readout_id]
    graph_summary = {
        "neurons": len(neurons),
        "aggregated_connections": len(edges),
        "summed_contact_count": int(edges["Connectivity"].sum()),
        "input_neurons": len(input_ids),
    }
    del edges

    spec = importlib.util.spec_from_file_location("pinned_flywire_model", inputs["model.py"])
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    params = dict(model.default_params)
    params["t_run"] = protocol["duration_ms"] * ms
    params["r_poi"] = protocol["stimulation_Hz"] * Hz
    params["n_run"] = trials
    output.mkdir(parents=True)
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    (output / "status.json").write_text('{"status": "running"}\n')
    event_frames = []
    trial_rows = []
    neuron_counts = np.zeros((trials, len(ids)), dtype=np.uint32)
    control_spikes = 0
    trial_seeds = []
    try:
        for condition, condition_trials in [("control", 1), ("sugar_100Hz", trials)]:
            start_scope()
            defaultclock.dt = protocol["time_step_ms"] * ms
            prefs.codegen.target = "cython"
            neu, syn, monitor = model.create_model(comp, con, params)
            stimulation = []
            if condition != "control":
                stimulation, neu = model.poi(
                    neu, [mapping[value] for value in input_ids], [], params
                )
            network = Network(neu, syn, monitor, *stimulation)
            network.store("initial")
            for trial in range(condition_trials):
                trial_started = perf_counter()
                network.restore("initial")
                trial_seed = protocol["seed"] + trial
                seed(trial_seed)
                network.run(params["t_run"])
                spike_indices = np.asarray(monitor.i, dtype=np.int64)
                times = np.asarray(monitor.t / ms)
                counts = np.bincount(spike_indices, minlength=len(ids))
                if condition == "control":
                    control_spikes = len(times)
                else:
                    neuron_counts[trial] = counts
                    trial_seeds.append(trial_seed)
                row = {
                    "condition": condition, "trial": trial, "seed": trial_seed,
                    "total_spikes": len(times),
                    "active_neurons": int(np.count_nonzero(counts)),
                    "mn9_spikes": int(counts[readout_index]),
                    "mn9_rate_Hz": int(counts[readout_index]) / (protocol["duration_ms"] / 1000),
                    "wall_seconds": perf_counter() - trial_started,
                }
                trial_rows.append(row)
                print(json.dumps(row), flush=True)
                if len(times):
                    event_frames.append(pd.DataFrame({
                        "time_ms": times, "trial": trial,
                        "flywire_id": ids[spike_indices], "condition": condition,
                    }))
            del network, neu, syn, monitor, stimulation
        readout_counts = [int(value) for value in neuron_counts[:, readout_index]]
        result = acceptance(readout_counts, control_spikes, protocol["trial_count"])
        if not event_frames:
            raise ValueError("No spikes recorded in any condition")
        pd.concat(event_frames, ignore_index=True).to_parquet(output / "spikes.parquet", index=False)
        pd.DataFrame(trial_rows).to_csv(output / "trials.csv", index=False)
        rates = neuron_counts / (protocol["duration_ms"] / 1000)
        pd.DataFrame({
            "flywire_id": ids,
            "mean_rate_Hz": rates.mean(axis=0),
            "std_rate_Hz": rates.std(axis=0),
            "active_trial_count": np.count_nonzero(neuron_counts, axis=0),
        }).to_parquet(output / "neuron_rates.parquet", index=False)
        summary = {
            "experiment_id": protocol["id"],
            "upstream_commit": protocol["upstream_commit"],
            "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "graph": graph_summary, "acceptance": result,
            "mn9_mean_rate_Hz": float(rates[:, readout_index].mean()),
            "mn9_std_rate_Hz": float(rates[:, readout_index].std()),
            "trial_seeds": trial_seeds, "wall_seconds": perf_counter() - started,
            "peak_rss_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "python": platform.python_version(),
            "dependencies": {
                package: importlib.metadata.version(package)
                for package in ["brian2", "numpy", "pandas", "scipy", "pyarrow", "Cython"]
            },
            "implementation": (
                "Unmodified upstream equations, parameters, create_model and poi helpers; "
                "serial trials restore initial state and reseed explicitly instead of joblib "
                "rebuilding the network. One additional no-input control. No full-figure claim."
            ),
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "status.json").write_text(json.dumps(result, indent=2) + "\n")
        if not result["passed"] and result["protocol_complete"]:
            raise ValueError("Published MN9 activation acceptance criterion failed; inspect recorded results")
    except Exception as error:
        (output / "status.json").write_text(json.dumps({
            "status": "failed", "error_type": type(error).__name__, "error": str(error),
            "completed_trial_records": len(trial_rows),
        }, indent=2) + "\n")
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--trials", type=int, help="Reduced trials for an explicitly incomplete smoke test")
    args = parser.parse_args()
    try:
        output = run(args.data_dir, args.run_name, args.trials)
    except (OSError, ValueError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
