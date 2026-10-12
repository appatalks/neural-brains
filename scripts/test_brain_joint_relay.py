"""Offline genuine brain spikes -> assumed VNC relay -> isolated FlyBody joint."""

import argparse
import hashlib
import json
from pathlib import Path

from bdn2_relay import CountRelay, DECAY_S, MODEL_CURRENT_PER_SPIKE, SCOPE as RELAY_SCOPE
from datasets import ROOT
from export_bdn2_packets import BDN2_IDS, CASES as BRAIN_CASES, MATCHED_CASES, walking_ids
from fly_activity import ActivityReader
from test_bdn2_vnc import rate_derivative
from test_vnc_joint import trial, physical_rate_trace, MAX_TORQUE
from vnc_reference import network_inputs, SAMPLE_DT_S


EXTRA_CASES = ("relay-disconnect", "vnc-mn-silence", "motor-disconnect", "feedback-cut")
SCOPE = (
    "Evoked model-generated female FlyWire BDN2 spikes -> explicitly assumed "
    "interval-boundary cross-specimen current relay -> measured male MANC "
    "topology with assumed continuous rate dynamics -> assumed recruitment/local "
    "feedback and one real FlyBody hinge on an external fixture. Offline replay, "
    "not natural sensory control, reconstructed muscles, brain-body sensory "
    "feedback, spontaneous walking or autonomous gait."
)


def integrate_packets(weights, params, motor, responses, connected=True, silence_motor=False,
                      current_per_spike=MODEL_CURRENT_PER_SPIKE, decay_s=DECAY_S):
    import math
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.sparse import csr_matrix

    if len(responses) != 100 or type(silence_motor) is not bool:
        raise ValueError("Relay integration requires exactly100validated10ms packets and explicit motor state")
    n = len(weights)
    if (np.shape(weights) != (n, n) or not np.isfinite(weights).all()
            or type(motor) is not int or not 4 <= motor < n
            or set(params) != {"tau", "gain", "threshold", "cap"}
            or any(np.shape(value) != (n,) or not np.isfinite(value).all()
                   or (np.asarray(value) <= 0).any() for value in params.values())):
        raise ValueError("Invalid relay VNC circuit or parameters")
    relay = CountRelay(connected, current_per_spike, decay_s)
    times = np.arange(1001)*SAMPLE_DT_S
    rates = np.empty((n, len(times)))
    state = np.zeros(n)
    weighted = csr_matrix(.03*weights.T)
    deliveries = []
    for interval, response in enumerate(responses):
        relay.validate(response)
        start, end = interval*.01, (interval+1)*.01
        if abs(response["neuron_activity"]["start_ms"]-start*1000) > 1e-7:
            raise ValueError("Packet start does not match the VNC integration interval")
        current = relay.current

        def rhs(time, values):
            applied = np.zeros(n)
            applied[0] = current*math.exp(-(time-start)/relay.decay_s)
            derivative = rate_derivative(values, applied, weighted, params)
            if silence_motor:
                derivative[motor] = -values[motor]/params["tau"][motor]
            return derivative

        result = solve_ivp(rhs, (start, end), state, method="RK45",
                           rtol=2e-9, atol=5e-12, max_step=.0002, dense_output=True)
        if not result.success:
            raise RuntimeError(f"Spike-driven VNC integration failed: {result.message}")
        selected = (times >= start-1e-12) & (times <= end+1e-12)
        rates[:, selected] = result.sol(times[selected])
        state = result.y[:, -1]
        deliveries.append(relay.accept(response))
    if not np.isfinite(rates).all() or rates.min() < -1e-8:
        raise RuntimeError("Spike-driven VNC produced invalid raw rates; no success fallback applied")
    return times, rates, deliveries


def load_packets(directory, matched_stimulus=False):
    protocol = json.loads((directory/"protocol.json").read_text())
    summary = json.loads((directory/"summary.json").read_text())
    seeds = protocol.get("seeds")
    labels = {"sham", "reset-replay", "no-input", "intact recruitment", "bpn-cut",
              "dn-silence", "FG suppression", "pre-FG exact parity"}
    cases = MATCHED_CASES if matched_stimulus else BRAIN_CASES
    if matched_stimulus:
        labels |= {"matched FG external stream", "FG output cut releases inhibition", "pre-FGcut exact parity"}
    required_seeds = 2 if matched_stimulus else 3
    if (not isinstance(seeds, list) or len(seeds) != required_seeds or len(set(seeds)) != required_seeds
            or any(type(seed) is not int or seed < 0 for seed in seeds)
            or protocol.get("cases") != list(cases) or protocol.get("bdn2_ids") != BDN2_IDS
            or matched_stimulus and protocol.get("matched_external_stimulus") is not True
            or protocol.get("duration_ms") != 1000 or protocol.get("interval_ms") != 10):
        raise ValueError("Spike-driven physical test requires the frozen complete brain protocol")
    checks = summary.get("checks")
    expected_checks = {(seed, label) for seed in seeds for label in labels}
    if (summary.get("status") != "passed" or not isinstance(checks, list)
            or len(checks) != len(expected_checks)
            or any(not isinstance(check, dict) or check.get("passed") is not True for check in checks)
            or {(check.get("seed"), check.get("check")) for check in checks} != expected_checks):
        raise ValueError("Brain export has not passed every predeclared causal control")
    reports = json.loads((directory/"results.json").read_text())
    expected_reports = {(seed, case) for seed in seeds for case in cases}
    if (len(reports) != len(expected_reports)
            or {(row["seed"], row["case"]) for row in reports} != expected_reports):
        raise ValueError("Brain export is missing or duplicating a case")
    loaded = {}
    for seed in seeds:
        metadata = json.loads((directory/f"seed-{seed}-metadata.json").read_text())
        walking_ids(metadata)
        for case in cases:
            report = next(row for row in reports if row["seed"] == seed and row["case"] == case)
            name = f"seed-{seed}-{case}.jsonl"
            content = (directory/name).read_bytes()
            if report["packet_file"] != name or hashlib.sha256(content).hexdigest() != report["packet_file_sha256"]:
                raise ValueError("Raw neural packet file differs from its recorded hash")
            responses = [json.loads(line) for line in content.decode().splitlines()]
            if len(responses) != 100:
                raise ValueError("Expected100neural intervals")
            reader = ActivityReader(metadata)
            reader.episode = responses[0]["neuron_activity"]["episode"]
            for response in responses:
                reader.accept(response)
            loaded[seed, case] = responses
        if matched_stimulus:
            fg_reports = [row for row in reports if row["seed"] == seed and
                          row["case"] in ("fg-coactivation", "fg-output-cut")]
            hashes = []
            for report in fg_reports:
                import numpy as np
                with np.load(directory/f"seed-{seed}-{report['case']}-stimulus.npz", allow_pickle=False) as events:
                    hashes.append(hashlib.sha256(events["channels"].tobytes()+events["ticks"].tobytes()).hexdigest())
                if hashes[-1] != report["external_stimulus_sha256"]:
                    raise ValueError("Matched external stimulus file changed")
            if len(set(hashes)) != 1:
                raise ValueError("FG controls do not share exact external activation events")
    return protocol, loaded


def run(data_dir, packets, output):
    import numpy as np
    data_dir, packets, output = [path.expanduser().resolve() for path in (data_dir, packets, output)]
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, packets, output)) or output.exists():
        raise ValueError("Use external verified data/packets and a new external joint-relay output")
    source_protocol, loaded = load_packets(packets)
    weights, rows, variants, motor, provenance = network_inputs(data_dir)
    params = variants["saved-336"]
    output.mkdir(parents=True)
    cases = (*BRAIN_CASES, *EXTRA_CASES)
    protocol = {
        "scope": SCOPE, "cases": cases, "brain_seeds": source_protocol["seeds"],
        "source_bdn2_root_id": BDN2_IDS["left"], "matched_manc_bdn2_body_id": "10093",
        "motor_body_id": rows[motor]["bodyId"], "vnc_parameters": "saved-336, no gain fitting",
        "relay": {"current_per_spike": MODEL_CURRENT_PER_SPIKE, "decay_s": DECAY_S, "scope": RELAY_SCOPE},
        "delivery": "Integrate the preceding VNC interval before accepting its packet; no retroactive spike timestamps",
        "brain_protocol_sha256": hashlib.sha256((packets/"protocol.json").read_bytes()).hexdigest(),
        "vnc_provenance": provenance,
        "predeclared_checks": [
            "Intact pairedjoint response>0.001rad relative to noinput at all brain seeds.",
            "Sham/reset exact allcell-rate and qpos/qvel/control/force replay.",
            "BrainBPNcut/BDNsilence/relaycut/VNCMNsilence/motorcut exact noinput physical parity.",
            "No motor rate before first delivered leftBDN2 interval; clocks exactly1000ms.",
            "FG coactivation reduces delivered source counts, VNC motor integral and peak activation.",
            "Feedbackcut zero added feedback with>0.0001rad motion difference.",
            "Fixture<0.01cm, torque<=0.002 and joint source bounds+0.02rad.",
        ],
        "code_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                        for name in ("test_brain_joint_relay.py", "bdn2_relay.py", "test_vnc_joint.py")},
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    checks, results = [], []
    try:
        for seed in source_protocol["seeds"]:
            outcomes, angles, motor_signals, rate_hashes = {}, {}, {}, {}
            for case in cases:
                responses = loaded[seed, case if case in BRAIN_CASES else "intact"]
                times, rates, deliveries = integrate_packets(
                    weights, params, motor, responses, connected=case != "relay-disconnect",
                    silence_motor=case == "vnc-mn-silence")
                directory = output/f"seed-{seed}-{case}"
                directory.mkdir()
                np.savez_compressed(directory/"vnc-rates.npz", time_s=times, rates=rates)
                (directory/"deliveries.json").write_text(json.dumps(deliveries, indent=2)+"\n")
                rate_hashes[case] = hashlib.sha256(rates.tobytes()).hexdigest()
                signal, diagnostics = physical_rate_trace(rates[motor].copy())
                motor_signals[case] = signal
                bench_case = case if case in ("sham", "reset-replay", "motor-disconnect", "feedback-cut") else "intact"
                physical, angles[case] = trial(signal, bench_case, directory)
                first = next((row["delivery_ms"] for row in deliveries if row["delivered_count"]), None)
                causal = np.array_equal(signal[times*1000 <= first], np.zeros_like(signal[times*1000 <= first])) if first is not None else np.array_equal(signal, np.zeros_like(signal))
                checks.append({"seed": seed, "case": case, "check": "causal delivery", "passed": bool(causal)})
                outcomes[case] = {**physical, "case": case, "brain_seed": seed,
                                  "source_spikes": sum(row["source_count"] for row in deliveries),
                                  "first_delivery_ms": first,
                                  "motor_rate_integral": float(np.trapz(signal, times)),
                                  "source_rate_diagnostics": diagnostics, "scope": SCOPE}
                results.append(outcomes[case])
                (directory/"summary.json").write_text(json.dumps(outcomes[case], indent=2)+"\n")
                (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                print(seed, case, outcomes[case]["source_spikes"], outcomes[case]["maximum_activation"],
                      outcomes[case]["final_joint_rad"], flush=True)
            base, intact = outcomes["no-input"], outcomes["intact"]
            difference = float(np.max(np.abs(angles["intact"]-angles["no-input"])))
            checks.append({"seed": seed, "check": "paired response", "maximum_difference_rad": difference,
                           "passed": difference > .001 and intact["maximum_activation"] > 0})
            for case in ("sham", "reset-replay"):
                checks.append({"seed": seed, "check": case,
                               "passed": outcomes[case]["physical_sha256"] == intact["physical_sha256"]
                               and rate_hashes[case] == rate_hashes["intact"]})
            for case in ("bpn-cut", "dn-silence", "relay-disconnect", "vnc-mn-silence", "motor-disconnect"):
                checks.append({"seed": seed, "check": case,
                               "passed": outcomes[case]["physical_sha256"] == base["physical_sha256"]})
            fg = outcomes["fg-coactivation"]
            checks.append({"seed": seed, "check": "FG suppression transfer",
                           "passed": fg["source_spikes"] < intact["source_spikes"]
                           and fg["motor_rate_integral"] < intact["motor_rate_integral"]
                           and fg["maximum_activation"] < intact["maximum_activation"]})
            difference = float(np.max(np.abs(angles["feedback-cut"]-angles["intact"])))
            checks.append({"seed": seed, "check": "feedback removal", "maximum_difference_rad": difference,
                           "passed": difference > .0001 and outcomes["feedback-cut"]["maximum_local_feedback_torque"] == 0})
            checks.append({"seed": seed, "check": "physical bounds",
                           "passed": all(row["maximum_fixture_drift_cm"] < .01 and row["maximum_torque"] <= MAX_TORQUE
                                         and row["minimum_joint_rad"] >= row["joint_limits_rad"][0]-.02
                                         and row["maximum_joint_rad"] <= row["joint_limits_rad"][1]+.02
                                         for row in outcomes.values())})
        summary = {"status": "passed" if all(check["passed"] for check in checks) else "failed",
                   "checks": checks, "trials": len(results), "scope": SCOPE, "normal_gait_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if summary["status"] != "passed":
            raise RuntimeError("Brain-spike relay/joint controls failed; full results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--packets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.packets_dir, args.output_dir)
