"""Bounded evoked walking/halting neural-path experiments; no physical decoder."""

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from time import perf_counter

from audit_walking_paths import primary_populations
from datasets import CATALOG, ROOT
from fly_circuit_interventions import outgoing_edge_indices
from run_flywire_sugar import PROTOCOL, verified_inputs


SEEDS = (420, 421, 422, 425)
CASES = (
    ("no-input", (), None, None, None),
    ("P9", ("P9",), None, None, None),
    ("P9-sham", ("P9",), None, "sham:oDN1", None),
    ("P9-FG", ("P9", "FG"), None, None, None),
    ("P9-BB", ("P9", "BB"), None, None, None),
    ("P9-BRK", ("P9", "BRK"), None, None, None),
    ("P9-cut", ("P9",), "P9", None, None),
    ("P9-output-silence", ("P9",), None, "silence:oDN1", None),
    ("BPN", ("BPN",), None, None, None),
    ("BPN-sham", ("BPN",), None, "sham:BDN2", None),
    ("BPN-FG", ("BPN", "FG"), None, None, None),
    ("BPN-BB", ("BPN", "BB"), None, None, None),
    ("BPN-BRK", ("BPN", "BRK"), None, None, None),
    ("BPN-cut", ("BPN",), "BPN", None, None),
    ("BPN-output-silence", ("BPN",), None, "silence:BDN2", None),
    ("BDN2-direct", ("BDN2",), None, None, None),
    ("BDN2-direct-silence", ("BDN2",), None, "silence:BDN2", None),
    ("P9-delayed-FG", ("P9",), None, None, "FG"),
    ("BPN-delayed-FG", ("BPN",), None, None, "FG"),
    ("FG-only", ("FG",), None, None, None),
    ("BB-only", ("BB",), None, None, None),
    ("BRK-only", ("BRK",), None, None, None),
)
SUGAR_CASES = (
    ("no-input", (), None, None, None),
    ("sugar-only", ("sugar",), None, None, None),
    ("sugar-cut", ("sugar",), "sugar", None, None),
    *((name, active, cut, clamp, None)
      for source in ("P9", "BPN")
      for name, active, cut, clamp in (
          (source, (source,), None, None),
          (source+"-sugar", (source, "sugar"), None, None),
          (source+"-sugar-FGcut", (source, "sugar"), "FG", None),
          (source+"-sugar-BBcut", (source, "sugar"), "BB", None),
          (source+"-sugar-FGsilence", (source, "sugar"), None, "silence:FG"),
          (source+"-sugar-FGsham", (source, "sugar"), None, "sham:FG"),
      )),
)


def evaluate(rows):
    by_key = {(row["seed"], row["case"]): row for row in rows}
    seeds = sorted({row["seed"] for row in rows})
    expected = {(seed, case[0]) for seed in seeds for case in CASES}
    if not seeds or len(by_key) != len(rows) or set(by_key) != expected:
        raise ValueError("Walking causal results must contain every case exactly once per seed")
    checks = []
    for seed in seeds:
        def check(name, passed):
            checks.append({"seed": seed, "check": name, "passed": bool(passed)})

        check("no-input silent", by_key[seed, "no-input"]["network_spikes"] == 0)
        for source, target in (("P9", "oDN1"), ("BPN", "BDN2")):
            intact = by_key[seed, source]
            sham = by_key[seed, source+"-sham"]
            cut = by_key[seed, source+"-cut"]
            silenced = by_key[seed, source+"-output-silence"]
            fg = by_key[seed, source+"-FG"]
            delayed = by_key[seed, source+"-delayed-FG"]
            check(source+" recruits "+target, intact["population_spikes"][target] > 0)
            check(source+" exact sham/reset parity", intact["counts_sha256"] == sham["counts_sha256"])
            check(source+" source cut isolates genuine source spikes",
                  cut["network_spikes"] == cut["population_spikes"][source] > 0)
            check(source+" output clamp prevents target spikes",
                  silenced["population_spikes"][target] == 0 and silenced["population_spikes"][source] > 0)
            check(source+" FG suppresses target", fg["population_spikes"][target] < intact["population_spikes"][target])
            check(source+" delayed FG exact pre-intervention parity",
                  delayed["halves"][0]["counts_sha256"] == intact["halves"][0]["counts_sha256"])
            check(source+" delayed FG suppresses subsequent target",
                  delayed["halves"][1]["population_spikes"][target] <
                  intact["halves"][1]["population_spikes"][target])
        check("BB suppresses P9 output",
              by_key[seed, "P9-BB"]["population_spikes"]["oDN1"] < by_key[seed, "P9"]["population_spikes"]["oDN1"])
        check("FG suppresses BPN output more than BB",
              by_key[seed, "BPN-FG"]["population_spikes"]["BDN2"] <
              by_key[seed, "BPN-BB"]["population_spikes"]["BDN2"])
        check("direct BDN2 drive generates actual spikes",
              by_key[seed, "BDN2-direct"]["population_spikes"]["BDN2"] > 0)
        check("clamp blocks direct-input spikes as well as recurrent input",
              by_key[seed, "BDN2-direct-silence"]["network_spikes"] == 0)
    return checks


def evaluate_sugar(rows):
    by_key = {(row["seed"], row["case"]): row for row in rows}
    seeds = sorted({row["seed"] for row in rows})
    expected = {(seed, case[0]) for seed in seeds for case in SUGAR_CASES}
    if not seeds or len(by_key) != len(rows) or set(by_key) != expected:
        raise ValueError("Sugar causal results must contain every case exactly once per seed")
    checks = []
    for seed in seeds:
        def check(name, passed):
            checks.append({"seed": seed, "check": name, "passed": bool(passed)})

        sugar = by_key[seed, "sugar-only"]
        cut = by_key[seed, "sugar-cut"]
        check("no-input silent", by_key[seed, "no-input"]["network_spikes"] == 0)
        check("sugar recruits FG more than BB",
              sugar["population_spikes"]["FG"] > sugar["population_spikes"]["BB"])
        check("sugar-cut leaves only sensory source spikes",
              cut["network_spikes"] == cut["population_spikes"]["sugar"] > 0
              and cut["population_spikes"]["FG"] == 0 and cut["mn9_spikes"] == 0)
        for source, target in (("P9", "oDN1"), ("BPN", "BDN2")):
            intact = by_key[seed, source+"-sugar"]
            fgcut = by_key[seed, source+"-sugar-FGcut"]
            silenced = by_key[seed, source+"-sugar-FGsilence"]
            sham = by_key[seed, source+"-sugar-FGsham"]
            check(source+" sugar suppresses descending output",
                  intact["population_spikes"][target] < by_key[seed, source]["population_spikes"][target])
            check(source+" FG output cut releases inhibition",
                  fgcut["population_spikes"][target] > intact["population_spikes"][target]
                  and fgcut["population_spikes"]["FG"] > 0)
            check(source+" FG clamp releases inhibition with zero FG spikes",
                  silenced["population_spikes"][target] > intact["population_spikes"][target]
                  and silenced["population_spikes"]["FG"] == 0)
            check(source+" exact FG sham parity", sham["counts_sha256"] == intact["counts_sha256"])
    return checks


def run(data_dir, output, seeds=SEEDS, timestep_ms=.05, experiment="walking"):
    import numpy as np
    from brian2 import Hz, Network, SpikeMonitor, defaultclock, ms, prefs, seed, start_scope

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose verified external inputs and a new external experiment directory")
    if (not seeds or len(seeds) > 4 or len(set(seeds)) != len(seeds)
            or any(type(value) is not int or value < 0 for value in seeds)):
        raise ValueError("Bounded pilot requires one to four distinct nonnegative seeds")
    if timestep_ms not in (.05, .1):
        raise ValueError("Use the paper's 0.05 ms or preserved live 0.1 ms timestep")
    if experiment not in {"walking", "sugar"}:
        raise ValueError("Choose the frozen walking or sugar causal protocol")
    cases = CASES if experiment == "walking" else SUGAR_CASES
    baseline_protocol = json.loads(PROTOCOL.read_text())
    datasets = {row["id"]: row for row in json.loads(CATALOG.read_text())["datasets"]}
    inputs = verified_inputs(data_dir, datasets["flywire-model-630"])
    annotations = verified_inputs(data_dir, datasets["flywire-annotations-630-v1.1.0"])
    primary = verified_inputs(data_dir, datasets["walking-halting-primary-identities-2024"])
    with inputs["2023_03_23_completeness_630_final.csv"].open() as stream:
        reader = csv.reader(stream)
        next(reader)
        ids = [row[0] for row in reader]
    if len(ids) != 127400 or len(set(ids)) != len(ids):
        raise ValueError("Walking experiments require the preserved complete model")
    with annotations["Supplemental_file1_annotations.tsv"].open() as stream:
        annotation_by_id = {row["root_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
    model_ids = set(ids)
    populations, _ = primary_populations(primary["41586_2024_7854_MOESM4_ESM.xlsx"], annotation_by_id, model_ids)
    if experiment == "sugar":
        sugar_ids = baseline_protocol["input_ids"]
        if any(value not in model_ids for value in sugar_ids):
            raise ValueError("Verified sugar input ID is absent from the preserved model")
        populations["sugar"] = [{"root_id": value, "population": "sugar"} for value in sugar_ids]
    mapping = {value: index for index, value in enumerate(ids)}
    readout_index = mapping[baseline_protocol["readout_id"]]
    indices = {name: [mapping[row["root_id"]] for row in group] for name, group in populations.items()}
    output.mkdir(parents=True)
    started = perf_counter()
    protocol = {
        "seeds": list(seeds),
        "prospective_seed": (425 if experiment == "walking" else 426)
        if (425 if experiment == "walking" else 426) in seeds else None,
        "timestep_ms": timestep_ms,
        "duration_ms": 1000, "halves_ms": 500, "input_rate_Hz": 150, "sugar_rate_Hz": 100,
        "experiment": experiment, "populations": populations, "cases": cases,
        "predeclared_checks": [
            "Each source recruits its descending target; exact sham/reset and pre-delayed-intervention count parity.",
            "No input is silent; source chemical-output cut leaves only directly stimulated source spikes.",
            "FG suppresses oDN1/BDN2; BB suppresses P9 output; FG suppresses BPN target more than BB.",
            "Target voltage/synaptic-state clamp blocks recurrent and directly injected spikes.",
        ] if experiment == "walking" else [
            "Sugar GRNs recruit FG more strongly than BB; sugar source-output cut isolates sensory spikes.",
            "Sugar suppresses walking target output; FG chemical-output cut and voltage clamp release inhibition.",
            "FG cut preserves FG spikes; FG clamp eliminates FG spikes; identity sham exactly preserves counts.",
        ],
        "code_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                        for name in ("test_walking_causality.py", "audit_walking_paths.py",
                                     "fly_circuit_interventions.py", "run_flywire_sugar.py")},
        "input_receipts": {name: json.loads((path.parent/"receipt.json").read_text())
                           for name, path in {**inputs, **primary}.items()},
        "scope": "Evoked causality inside original chemical LIF model, BPN CL210 subset only. Not spontaneous motivation, VNC braking, natural walking or a reproduction of the published modified model.",
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"loading"}\n')
    results = []
    try:
        spec = importlib.util.spec_from_file_location("walking_pinned_model", inputs["model.py"])
        model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        start_scope()
        defaultclock.dt = timestep_ms*ms
        prefs.codegen.target = "cython"
        params = dict(model.default_params, r_poi=150*Hz)
        neurons, synapses, unused = model.create_model(
            inputs["2023_03_23_completeness_630_final.csv"],
            inputs["2023_03_23_connectivity_630_final.parquet"], params)
        del unused
        if len(synapses) != 14687178:
            raise ValueError("Walking network edge count differs from the preserved snapshot")
        monitor = SpikeMonitor(neurons, record=False)
        stimulation = {}
        for name, targets in indices.items():
            drive_params = dict(params, r_poi=100*Hz) if name == "sugar" else params
            stimulation[name], _ = model.poi(neurons, targets, [], drive_params)
            for item in stimulation[name]:
                item.active = False
        neurons.rfc = params["t_rfc"]
        network = Network(neurons, synapses, monitor,
                          *(item for group in stimulation.values() for item in group))
        clamps = {}
        for name in ("BDN2", "oDN1", "FG"):
            for kind, code in (("silence", "v = v_0; g = 0*mV"), ("sham", "v = v; g = g")):
                group = []
                for index in indices[name]:
                    operation = neurons[index:index+1].run_regularly(code, when="before_thresholds")
                    operation.active = False
                    group.append(operation)
                    network.add(operation)
                clamps[kind+":"+name] = group
        source_indices = synapses.i[:]
        cut_edges = {name: outgoing_edge_indices(source_indices, indices[name])
                     for name in {case[2] for case in cases if case[2] is not None}}
        network.store("initial")
        (output/"status.json").write_text('{"status":"running"}\n')
        for seed_value in seeds:
            for case, active, cut, clamp, delayed in cases:
                network.restore("initial")
                seed(seed_value)
                for group in clamps.values():
                    for operation in group:
                        operation.active = False
                if clamp is not None:
                    for operation in clamps[clamp]:
                        operation.active = True
                if cut is not None:
                    if not len(cut_edges[cut]):
                        raise ValueError("Walking source has no chemical output edges")
                    synapses.w[cut_edges[cut]] = 0*params["w_syn"]
                halves = []
                for half in range(2):
                    enabled = set(active) | ({delayed} if half == 1 and delayed is not None else set())
                    for name, group in stimulation.items():
                        for item in group:
                            item.active = name in enabled
                        if name in enabled:
                            neurons.rfc[indices[name]] = 0*ms
                    before = monitor.count[:].copy()
                    network.run(500*ms)
                    counts = np.asarray(monitor.count[:]-before, dtype=np.int64)
                    halves.append({
                        "counts_sha256": hashlib.sha256(counts.tobytes()).hexdigest(),
                        "population_spikes": {name: int(counts[group].sum()) for name, group in indices.items()},
                    })
                counts = np.asarray(monitor.count[:], dtype=np.int64)
                if int(counts.sum()) != int(monitor.num_spikes) or abs(float(network.t/ms)-1000) > 1e-6:
                    raise RuntimeError("Walking spike count or simulation clock invariant failed")
                nonzero = np.flatnonzero(counts)
                np.savez_compressed(output/f"seed-{seed_value}-{case}-counts.npz",
                                    indices=nonzero, counts=counts[nonzero])
                row = {
                    "seed": seed_value, "case": case, "network_spikes": int(counts.sum()),
                    "mn9_spikes": int(counts[readout_index]),
                    "population_spikes": {name: int(counts[group].sum()) for name, group in indices.items()},
                    "counts_sha256": hashlib.sha256(counts.tobytes()).hexdigest(),
                    "halves": halves,
                }
                results.append(row)
                (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                print(f"seed={seed_value} case={case} total={row['network_spikes']} "
                      f"oDN1={row['population_spikes']['oDN1']} BDN2={row['population_spikes']['BDN2']}", flush=True)
        checks = evaluate(results) if experiment == "walking" else evaluate_sugar(results)
        passed = all(row["passed"] for row in checks)
        summary = {"status": "passed" if passed else "failed", "trials": len(results),
                   "checks": checks, "wall_seconds": perf_counter()-started,
                   "scope": protocol["scope"], "motor_controller_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if not passed:
            raise RuntimeError("Predeclared walking causal checks failed; full results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--timestep-ms", type=float, choices=(.05, .1), default=.05)
    parser.add_argument("--experiment", choices=("walking", "sugar"), default="walking")
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir, tuple(args.seeds), args.timestep_ms, args.experiment)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"ERROR: walking causal experiment failed: {error}\n")
