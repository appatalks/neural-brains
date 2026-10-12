"""Bounded evoked FlyWire walking-path spike packets for an isolated joint test."""

import argparse
import hashlib
import json
from pathlib import Path

from datasets import ROOT
from fly_activity import ActivityReader, validate_neuron_ids
from fly_brain_worker import Brain
from fly_circuit_interventions import outgoing_edge_indices


BDN2_IDS = {"left": "720575940612364530", "right": "720575940647228468"}
CASES = ("intact", "sham", "no-input", "bpn-cut", "dn-silence", "fg-coactivation", "reset-replay")
MATCHED_CASES = (*CASES, "fg-output-cut")
SEEDS = (420, 421, 430)


def walking_ids(metadata):
    rows = metadata.get("sensorimotor_candidates", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Walking source metadata must contain candidate records")
    bdn = [row for row in rows if row.get("population") == "BDN2"]
    if (len(bdn) != 2 or {row.get("side"): row.get("root_id") for row in bdn} != BDN2_IDS
            or any(not row.get("in_model") or row.get("ambiguous_type_correspondence") for row in bdn)):
        raise ValueError("Spike export requires the exact primary-verified BDN2 pair")
    result = {}
    for population, count in (("BPN", 12), ("FG", 2)):
        group = [row for row in rows if row.get("population") == population]
        ids = [row.get("root_id") for row in group]
        if (len(group) != count or len(set(ids)) != count
                or any(not row.get("in_model") or row.get("ambiguous_type_correspondence") for row in group)):
            raise ValueError(f"Spike export requires the primary-verified {population} population")
        result[population] = ids
    result["BDN2"] = list(BDN2_IDS.values())
    validate_neuron_ids([value for values in result.values() for value in values])
    return result


def fingerprint(responses):
    return hashlib.sha256(json.dumps([
        [response["neuron_activity"]["indices"], response["neuron_activity"]["counts"],
         response["sensorimotor_spikes"], response["brain_time_ms"]]
        for response in responses
    ], sort_keys=True).encode()).hexdigest()


def matched_events(seed_value, case):
    import numpy as np
    if type(seed_value) is not int or not 0 <= seed_value < 2**32 or case not in MATCHED_CASES:
        raise ValueError("Matched stimulus requires a declared case and32bit seed")
    generator = np.random.default_rng(seed_value)
    events = generator.random((10000, 14)) < .015
    steps = np.arange(10000)
    events[:, :12] &= ((steps >= 500) & (steps < 8000))[:, None]
    events[:, 12:] &= ((steps >= 3000) & (steps < 5000))[:, None]
    if case not in ("fg-coactivation", "fg-output-cut"):
        events[:, 12:] = False
    if case == "no-input":
        events[:] = False
    ticks, channels = np.nonzero(events)
    return channels.astype(np.int32), ticks.astype(np.int64)


def run(data_dir, output, seeds=SEEDS, matched_stimulus=False):
    from brian2 import Hz, PoissonInput, SpikeGeneratorGroup, Synapses, defaultclock, ms, mV

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose verified external inputs and a new external spike export")
    if not seeds or len(seeds) > 3 or len(set(seeds)) != len(seeds) or any(type(value) is not int or value < 0 for value in seeds):
        raise ValueError("Bounded export requires one to three distinct nonnegative brain seeds")
    if type(matched_stimulus) is not bool:
        raise ValueError("Matched stimulus must be explicitly enabled")
    cases = MATCHED_CASES if matched_stimulus else CASES
    output.mkdir(parents=True)
    protocol = {
        "schema_version": 1, "seeds": list(seeds), "cases": cases,
        "prospective_brain_seed": 430 if 430 in seeds else None,
        "matched_external_stimulus": matched_stimulus,
        "duration_ms": 1000, "interval_ms": 10, "BPN_rate_Hz": 150, "FG_rate_Hz": 150,
        "BPN_window_ms": [50, 800], "FG_window_ms": [300, 500], "bdn2_ids": BDN2_IDS,
        "scope": "Actual model-generated FlyWire630 LIF spikes under explicit BPN/FG Poisson interventions; not spontaneous behavior, calibrated sensory encoding or natural walking.",
        "predeclared_checks": [
            "Intact and sham/reset sparse counts exactly match at each identical seed.",
            "No-input network silent; intact leftBDN2 recruits while BPN input is active.",
            "BPN-output cut preserves source spikes and eliminates bothBDN2outputs.",
            "BDN2 voltage/synaptic-state clamp eliminates bothBDN2outputs while BPNfires.",
            "FG coactivation suppresses leftBDN2 within300..500ms; pre300ms exact count parity.",
        ] + ([
            "FGcoactivation/FGoutput-cut share exact external activation events.",
            "FG output cut preserves FGfiring and releases leftBDN2 inhibition in300..500ms.",
            "FGcoactivation/FGoutput-cut pre300ms sparse counts exactly match.",
        ] if matched_stimulus else []),
        "code_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                        for name in ("export_bdn2_packets.py", "fly_brain_worker.py", "fly_activity.py")},
        "research_refractory_rule": "As pinned model.poi: external Poisson targets BPN/FG have zero refractory period; all other cells retain their existing model rules.",
        "matched_stimulus_definition": "NumPy PCG64 seeded Bernoulli0.015per100us per14channels; fixed spike-generator activation events. FGcoactivation/FGoutput-cut use the exact same external event stream; recorded neuron spikes remain actual network responses." if matched_stimulus else None,
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    checks, reports = [], []
    try:
        for seed_value in seeds:
            brain = Brain(data_dir, seed_value, takeoff=True, telemetry=True, walking_readouts=True)
            populations = walking_ids(brain.metadata)
            mapping = {value: index for index, value in enumerate(brain.metadata["neuron_ids"])}
            neurons = brain.network["default_neurons"]
            synapses = brain.network["default_synapses"]
            inputs = {}
            stimulus = None
            if matched_stimulus:
                import numpy as np
                if abs(float(defaultclock.dt/ms)-.1) > 1e-12:
                    raise ValueError("Matched stimulus requires the verified0.1ms brain timestep")
                stimulus = SpikeGeneratorGroup(14, np.array([], dtype=np.int32), np.array([])*ms,
                                               name="research_matched_input")
                activation = Synapses(stimulus, neurons, "w : volt", on_pre="v_post += w",
                                      name="research_activation")
                targets = [mapping[value] for name in ("BPN", "FG") for value in populations[name]]
                activation.connect(i=np.arange(14), j=targets)
                activation.w = neurons.namespace["w_syn"]*neurons.namespace["f_poi"]
                neurons.rfc[targets] = 0*ms
                brain.network.add(stimulus, activation)
            else:
                for population in ("BPN", "FG"):
                    group = []
                    for value in populations[population]:
                        index = mapping[value]
                        driver = PoissonInput(neurons[index:index+1], "v", N=1, rate=150*Hz,
                                              weight=neurons.namespace["w_syn"]*neurons.namespace["f_poi"])
                        driver.active = False
                        neurons.rfc[index] = 0*ms
                        brain.network.add(driver)
                        group.append(driver)
                    inputs[population] = group
            clamps = {}
            for kind, code in (("sham", "v = v; g = g"), ("silence", "v = v_0; g = 0*mV")):
                group = []
                for value in populations["BDN2"]:
                    index = mapping[value]
                    operation = neurons[index:index+1].run_regularly(code, when="before_thresholds")
                    operation.active = False
                    brain.network.add(operation)
                    group.append(operation)
                clamps[kind] = group
            edges = outgoing_edge_indices(synapses.i[:], [mapping[value] for value in populations["BPN"]])
            fg_edges = outgoing_edge_indices(synapses.i[:], [mapping[value] for value in populations["FG"]])
            if not len(edges):
                raise ValueError("BPN source-output intervention requires measured chemical edges")
            brain.network.store("initial")
            reader = ActivityReader(brain.metadata)
            (output/f"seed-{seed_value}-metadata.json").write_text(json.dumps(brain.metadata)+"\n")
            observed = {}
            for case in cases:
                reset = brain.reset()
                reader.accept(reset, reset=True)
                for group in clamps.values():
                    for operation in group:
                        operation.active = False
                if case in ("sham", "dn-silence"):
                    for operation in clamps["sham" if case == "sham" else "silence"]:
                        operation.active = True
                cut_edges = edges if case == "bpn-cut" else fg_edges if case == "fg-output-cut" else None
                if cut_edges is not None:
                    if not len(cut_edges):
                        raise ValueError("Requested chemical-output cut has no edges")
                    synapses.w[cut_edges] = 0*mV
                    if any(synapses.w[cut_edges] != 0*mV):
                        raise RuntimeError("Requested chemical outputs were not disconnected")
                stream_hash = None
                if stimulus is not None:
                    channels, ticks = matched_events(seed_value, case)
                    stimulus.set_spikes(channels, ticks*.1*ms, sorted=True)
                    stream_hash = hashlib.sha256(channels.tobytes()+ticks.tobytes()).hexdigest()
                    np.savez_compressed(output/f"seed-{seed_value}-{case}-stimulus.npz",
                                        channels=channels, ticks=ticks)
                responses = []
                path = output/f"seed-{seed_value}-{case}.jsonl"
                with path.open("x") as log:
                    for interval in range(100):
                        start_ms = interval*10
                        for driver in inputs.get("BPN", []):
                            driver.active = case != "no-input" and 50 <= start_ms < 800
                        for driver in inputs.get("FG", []):
                            driver.active = case == "fg-coactivation" and 300 <= start_ms < 500
                        response = brain.step(10, False, False)
                        reader.accept(response)
                        if response["brain_time_ms"] != start_ms+10:
                            raise RuntimeError("Spike packet clock differs from the frozen stimulus schedule")
                        responses.append(response)
                        log.write(json.dumps(response)+"\n")
                observed[case] = responses
                counts = {name: sum(response["sensorimotor_spikes"][value]
                                    for response in responses for value in values)
                          for name, values in populations.items()}
                row = {"seed": seed_value, "case": case, "population_counts": counts,
                       "external_stimulus_sha256": stream_hash,
                       "left_bdn2_spikes": sum(response["sensorimotor_spikes"][BDN2_IDS["left"]] for response in responses),
                       "network_spikes": sum(response["network_spikes"] for response in responses),
                       "response_fingerprint": fingerprint(responses), "packet_file": path.name,
                       "packet_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                reports.append(row)
                (output/"results.json").write_text(json.dumps(reports, indent=2)+"\n")
                print(seed_value, case, counts, flush=True)
            by_case = {row["case"]: row for row in reports if row["seed"] == seed_value}
            for case in ("sham", "reset-replay"):
                checks.append({"seed": seed_value, "check": case,
                               "passed": by_case[case]["response_fingerprint"] == by_case["intact"]["response_fingerprint"]})
            checks.append({"seed": seed_value, "check": "no-input",
                           "passed": by_case["no-input"]["network_spikes"] == 0})
            checks.append({"seed": seed_value, "check": "intact recruitment",
                           "passed": by_case["intact"]["left_bdn2_spikes"] > 0})
            for case in ("bpn-cut", "dn-silence"):
                checks.append({"seed": seed_value, "check": case,
                               "passed": by_case[case]["population_counts"]["BPN"] > 0
                               and by_case[case]["population_counts"]["BDN2"] == 0})
            def window_count(case):
                return sum(response["sensorimotor_spikes"][BDN2_IDS["left"]]
                           for response in observed[case] if 300 <= response["neuron_activity"]["start_ms"] < 500)
            checks.append({"seed": seed_value, "check": "FG suppression",
                           "intact_spikes": window_count("intact"), "FG_spikes": window_count("fg-coactivation"),
                           "passed": window_count("fg-coactivation") < window_count("intact")})
            checks.append({"seed": seed_value, "check": "pre-FG exact parity",
                           "passed": fingerprint(observed["fg-coactivation"][:30]) == fingerprint(observed["intact"][:30])})
            if matched_stimulus:
                checks.append({"seed": seed_value, "check": "matched FG external stream",
                               "passed": by_case["fg-output-cut"]["external_stimulus_sha256"] ==
                               by_case["fg-coactivation"]["external_stimulus_sha256"]})
                checks.append({"seed": seed_value, "check": "FG output cut releases inhibition",
                               "passed": window_count("fg-output-cut") > window_count("fg-coactivation")
                               and by_case["fg-output-cut"]["population_counts"]["FG"] > 0})
                checks.append({"seed": seed_value, "check": "pre-FGcut exact parity",
                               "passed": fingerprint(observed["fg-output-cut"][:30]) ==
                               fingerprint(observed["fg-coactivation"][:30])})
        summary = {"status": "passed" if all(check["passed"] for check in checks) else "failed",
                   "checks": checks, "scope": protocol["scope"], "normal_worker_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if summary["status"] != "passed":
            raise RuntimeError("Predeclared brain spike export checks failed; results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--matched-stimulus", action="store_true")
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, tuple(args.seeds), args.matched_stimulus)
