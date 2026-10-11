"""Isolated FlyWire visual chemical-path disconnection experiment."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from datasets import ROOT
from fly_feeding import BrainClient
from fly_walking import external_output


CASES = (("intact", None, True), ("sham", None, True), ("LC4", "LC4", True),
         ("LPLC2", "LPLC2", True), ("both", "both", True), ("no_input", None, False))


def run(data_dir, output, seeds=(420, 421)):
    output = external_output(output)
    if not seeds or any(type(seed) is not int or seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Causal experiment requires distinct nonnegative integer seeds")
    output.mkdir(parents=True)
    (output/"status.json").write_text('{"status":"running"}\n')
    protocol = {
        "seeds": list(seeds), "duration_ms": 1000, "visual_stimulation_Hz": 100,
        "populations": ["LC4", "LPLC2"], "sugar_contact": False,
        "intervention": "Zero selected outgoing recurrent chemical weights; keep cell spikes, incoming inputs and Poisson stimulation",
        "predeclared_checks": [
            "Intact and sham outputs exactly equal at identical seed",
            "No-input network silent",
            "Both-population output disconnection leaves source spikes but no GF or candidate downstream spikes",
            "Reset preserves disconnection and replays outputs exactly",
        ],
        "scope": "Causality inside the approximate model only. Not calibrated physiology, physical steering or landing.",
        "code_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                        for name in ["fly_brain_worker.py", "fly_circuit_interventions.py", "test_visual_causality.py"]},
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    report = []
    try:
        for seed in seeds:
            reference = None
            for name, disconnect, stimulus in CASES:
                directory = output/f"seed-{seed}-{name}"
                directory.mkdir()
                brain = BrainClient(
                    ROOT/".venv/bin/python", data_dir, directory, seed, takeoff=True,
                    telemetry=True, disconnect_visual_output=disconnect,
                )
                try:
                    (directory/"metadata.json").write_text(json.dumps(brain.metadata)+"\n")
                    brain.begin_step(1000, False, stimulus)
                    response = brain.finish_step()
                    (directory/"response.json").write_text(json.dumps(response)+"\n")
                    source_indices = {brain.metadata["neuron_ids"].index(value)
                                      for value in brain.metadata["visual_input_ids"]}
                    packet = response["neuron_activity"]
                    source_spikes = sum(count for index, count in zip(packet["indices"], packet["counts"])
                                        if index in source_indices)
                    check = True
                    if name == "intact":
                        reference = response
                    elif name == "sham":
                        check = response == reference
                    elif name == "no_input":
                        check = response["network_spikes"] == 0
                    elif name == "both":
                        check = (
                            source_spikes > 0 and source_spikes == response["network_spikes"]
                            and sum(response["giant_fiber_spikes"].values()) == 0
                            and sum(response["sensorimotor_spikes"].values()) == 0
                        )
                        brain.reset()
                        brain.begin_step(1000, False, True)
                        replay = brain.finish_step()
                        (directory/"reset-replay.json").write_text(json.dumps(replay)+"\n")
                        check = check and (
                            replay["neuron_activity"]["indices"] == packet["indices"]
                            and replay["neuron_activity"]["counts"] == packet["counts"]
                            and replay["sensorimotor_spikes"] == response["sensorimotor_spikes"]
                            and replay["giant_fiber_spikes"] == response["giant_fiber_spikes"]
                        )
                    row = {
                        "seed": seed, "case": name, "check_passed": bool(check),
                        "network_spikes": response["network_spikes"], "visual_source_spikes": source_spikes,
                        "gf_spikes": response["giant_fiber_spikes"],
                        "sensorimotor_spikes": response["sensorimotor_spikes"],
                        "intervention": brain.metadata.get("research_intervention"),
                    }
                    report.append(row)
                    (output/"results.json").write_text(json.dumps(report, indent=2)+"\n")
                    if not check:
                        raise RuntimeError(f"Predeclared causal check failed for seed {seed}, case {name}")
                    print(f"seed={seed} case={name} network={row['network_spikes']} GF={sum(row['gf_spikes'].values())}", flush=True)
                finally:
                    brain.close()
        (output/"status.json").write_text('{"status":"passed"}\n')
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed", "error":str(error)})+"\n")
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[420, 421])
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir, tuple(args.seeds))
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"ERROR: visual causal experiment failed: {error}\n")


if __name__ == "__main__":
    main()
