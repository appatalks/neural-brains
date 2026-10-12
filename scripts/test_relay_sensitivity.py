"""Frozen relay-uncertainty grid, matched FG controls and separate held-out tests."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from datasets import ROOT
from export_bdn2_packets import BDN2_IDS
from test_brain_joint_relay import integrate_packets, load_packets
from test_vnc_joint import physical_rate_trace, trial, MAX_TORQUE
from vnc_reference import network_inputs


DEVELOPMENT = (420, 421)
HELD_OUT = (431, 432)


def candidates():
    return [
        {"id": f"mean-{mean}-tau-{round(tau*1000)}",
         "mean_drive_at_100Hz": mean, "decay_s": tau,
         "current_per_spike": mean/(100*tau),
         "preference_distance": abs(math.log2(mean/250))+abs(math.log2(tau/.04))}
        for mean in (125, 250, 500) for tau in (.02, .04, .08)
    ]


def select_candidate(rows):
    expected = {(seed, label) for seed in DEVELOPMENT for label in
                ("matched response", "matched FG suppression", "physical bounds",
                 "causal delivery", "legacy response")}
    eligible = [
        row for row in rows if row["passed"] is True
        and len(row.get("checks", [])) == len(expected)
        and {(check.get("seed"), check.get("check")) for check in row["checks"]} == expected
        and all(check.get("passed") is True for check in row["checks"])
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda row: (
        row["candidate"]["preference_distance"],
        row["candidate"]["mean_drive_at_100Hz"], row["candidate"]["decay_s"]))["candidate"]


def physical_bounds(row):
    return (
        row["maximum_fixture_drift_cm"] < .01 and row["maximum_torque"] <= MAX_TORQUE
        and row["minimum_joint_rad"] >= row["joint_limits_rad"][0]-.02
        and row["maximum_joint_rad"] <= row["joint_limits_rad"][1]+.02
    )


def export_matched(data_dir, output, seeds, log_path):
    with log_path.open("x") as log:
        result = subprocess.run([
            str(ROOT/".venv/bin/python"), str(ROOT/"scripts/export_bdn2_packets.py"),
            "--data-dir", str(data_dir), "--output-dir", str(output),
            "--matched-stimulus", "--seeds", *(str(seed) for seed in seeds),
        ], stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"Matched brain export failed; inspect {log_path}")
    return load_packets(output, matched_stimulus=True)


def run(data_dir, legacy_packets, output):
    import numpy as np

    data_dir, legacy_packets, output = [path.expanduser().resolve() for path in (data_dir, legacy_packets, output)]
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, legacy_packets, output)) or output.exists():
        raise ValueError("Use external verified data/legacy packets and a new uncertainty-test output")
    _, legacy = load_packets(legacy_packets)
    weights, _, variants, motor, provenance = network_inputs(data_dir)
    params = variants["saved-336"]
    output.mkdir(parents=True)
    grid = candidates()
    protocol = {
        "schema_version": 1, "scope": "Research uncertainty in an assumed spike-to-current relay, not physiology or autonomous walking.",
        "development_seeds": DEVELOPMENT, "held_out_seeds": HELD_OUT, "candidates": grid,
        "range_basis": "Half/equal/double published250model-unit tonic drive at100Hz;20/40/80ms decay spanning published20ms rate-cell time scale and prior40ms assumption. Not measured conductances.",
        "legacy_regression_seeds": DEVELOPMENT,
        "selection_rule": "All development checks required; minimize log2 distance from prior250mean/40ms; ties lowermean then shorterdecay. Never consult held-out responses to select or refit.",
        "predeclared_checks": [
            "Matched intact joint response>0.001rad relative to fixed no-input bench at both development seeds.",
            "Legacy420/421 intact response also>0.001rad; original failed001 remains failed.",
            "Matched FGoutput-cut preserves identical external input events and has greater source counts, VNC motor integral and physical activation integral than FGcoactivation.",
            "Every case respects fixture<0.01cm, torque<=0.002 and original joint range+0.02rad.",
            "Held-out431/432 only generated after selection.json is frozen, with no refitting.",
            "Held-out sham/reset exact neural-rate and physics hashes; all source/relay/motorcut physics match no-input.",
            "Held-out feedbackcut>0.0001rad difference and exactly0addedfeedback.",
            "All cases have0motorresponse before the first delivered packet.",
        ],
        "metric_boundary": "Integrated activation over1s for matched FG causality; old unmatched global-peak gate remains a reported diagnostic and is not reclassified as passed.",
        "fixed_parameters": "Saved336VNC rate parameters and priorjoint recruitment/torque/reflex/fixture unchanged.",
        "vnc_provenance": provenance,
        "legacy_protocol_sha256": hashlib.sha256((legacy_packets/"protocol.json").read_bytes()).hexdigest(),
        "code_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                        for name in ("test_relay_sensitivity.py", "export_bdn2_packets.py",
                                     "bdn2_relay.py", "test_brain_joint_relay.py", "test_vnc_joint.py")},
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"development-brain"}\n')
    results, checks = [], []
    try:
        baseline_dir = output/"fixed-no-input-bench"
        baseline_dir.mkdir()
        baseline, baseline_angles = trial(np.zeros(1001), "no-drive", baseline_dir)
        _, development = export_matched(data_dir, output/"development-packets", DEVELOPMENT,
                                        output/"development-brain.log")

        def evaluate_case(candidate, seed, case, responses, directory, relay_connected=True,
                          silence_motor=False, bench_case="intact"):
            directory.mkdir(parents=True)
            try:
                times, rates, deliveries = integrate_packets(
                    weights, params, motor, responses, connected=relay_connected,
                    silence_motor=silence_motor, current_per_spike=candidate["current_per_spike"],
                    decay_s=candidate["decay_s"])
                signal, diagnostics = physical_rate_trace(rates[motor].copy())
                row, angles = trial(signal, bench_case, directory)
                first = next((delivery["delivery_ms"] for delivery in deliveries if delivery["delivered_count"]), None)
                before = signal[times*1000 <= first] if first is not None else signal
                causal = bool(np.array_equal(before, np.zeros_like(before)))
                row.update({
                    "candidate": candidate["id"], "seed": seed, "case": case, "status": "completed",
                    "source_spikes": sum(delivery["source_count"] for delivery in deliveries),
                    "motor_rate_integral": float(np.trapz(signal, times)),
                    "rate_sha256": hashlib.sha256(rates.tobytes()).hexdigest(),
                    "causal_delivery": causal, "source_rate_diagnostics": diagnostics,
                })
                np.savez_compressed(directory/"vnc-rates.npz", time_s=times, rates=rates)
                (directory/"deliveries.json").write_text(json.dumps(deliveries)+"\n")
                (directory/"summary.json").write_text(json.dumps(row, indent=2)+"\n")
                return row, angles
            except RuntimeError as error:
                row = {"candidate": candidate["id"], "seed": seed, "case": case,
                       "status": "failed", "error": str(error)}
                (directory/"summary.json").write_text(json.dumps(row, indent=2)+"\n")
                print(f"WARNING: failed candidate case {candidate['id']} {seed} {case}: {error}", flush=True)
                return row, None

        def pair_checks(seed, rows, angles, legacy_angles=None):
            if any(row["status"] != "completed" for row in rows.values()):
                return [{"seed": seed, "check": "complete numerical/physical cases", "passed": False}]
            intact, fg, cut = rows["intact"], rows["fg-coactivation"], rows["fg-output-cut"]
            delta = float(np.max(np.abs(angles["intact"]-baseline_angles)))
            items = [
                {"seed": seed, "check": "matched response", "maximum_difference_rad": delta, "passed": delta > .001},
                {"seed": seed, "check": "matched FG suppression",
                 "passed": fg["source_spikes"] < cut["source_spikes"]
                 and fg["motor_rate_integral"] < cut["motor_rate_integral"]
                 and fg["activation_integral_s"] < cut["activation_integral_s"]},
                {"seed": seed, "check": "physical bounds", "passed": all(physical_bounds(row) for row in rows.values())},
                {"seed": seed, "check": "causal delivery", "passed": all(row["causal_delivery"] for row in rows.values())},
            ]
            if legacy_angles is not None:
                delta = float(np.max(np.abs(legacy_angles-baseline_angles)))
                items.append({"seed": seed, "check": "legacy response", "maximum_difference_rad": delta, "passed": delta > .001})
            return items

        development_results = []
        (output/"status.json").write_text('{"status":"development-grid"}\n')
        for candidate in grid:
            candidate_checks = []
            for seed in DEVELOPMENT:
                rows, angles = {}, {}
                for case in ("intact", "fg-coactivation", "fg-output-cut", "legacy-intact"):
                    responses = legacy[seed, "intact"] if case == "legacy-intact" else development[seed, case]
                    directory = output/"development-grid"/candidate["id"]/f"seed-{seed}-{case}"
                    rows[case], angles[case] = evaluate_case(candidate, seed, case, responses, directory)
                candidate_checks.extend(pair_checks(seed, rows, angles, angles.get("legacy-intact")))
            row = {"candidate": candidate, "checks": candidate_checks,
                   "passed": all(item["passed"] for item in candidate_checks)}
            development_results.append(row)
            (output/"development-results.json").write_text(json.dumps(development_results, indent=2)+"\n")
            print(candidate["id"], "development_passed="+str(row["passed"]), flush=True)
        selected = select_candidate(development_results)
        selection = {"candidate": selected, "development_passed": selected is not None,
                     "rule": protocol["selection_rule"], "held_out_evaluated": False}
        (output/"selection.json").write_text(json.dumps(selection, indent=2)+"\n")
        if selected is None:
            summary = {"status": "failed", "reason": "No candidate passed development; held-out data not generated",
                       "development_results": development_results, "normal_gait_modified": False}
            (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
            raise RuntimeError(summary["reason"])
        print("Frozen candidate:", selected, flush=True)
        frozen_hash = hashlib.sha256((output/"selection.json").read_bytes()).hexdigest()
        (output/"status.json").write_text('{"status":"held-out-brain"}\n')
        _, held_out = export_matched(data_dir, output/"held-out-packets", HELD_OUT,
                                     output/"held-out-brain.log")
        if hashlib.sha256((output/"selection.json").read_bytes()).hexdigest() != frozen_hash:
            raise RuntimeError("Selection changed after held-out generation; no validation allowed")
        (output/"status.json").write_text('{"status":"held-out-physical"}\n')
        for seed in HELD_OUT:
            rows, angles = {}, {}
            cases = ("intact", "fg-coactivation", "fg-output-cut", "sham", "reset-replay",
                     "no-input", "bpn-cut", "dn-silence", "relay-disconnect", "vnc-mn-silence",
                     "motor-disconnect", "feedback-cut")
            for case in cases:
                responses = held_out[seed, case if case in ("intact", "fg-coactivation", "fg-output-cut",
                                                           "sham", "reset-replay", "no-input", "bpn-cut", "dn-silence") else "intact"]
                bench_case = case if case in ("sham", "reset-replay", "motor-disconnect", "feedback-cut") else "intact"
                directory = output/"held-out"/f"seed-{seed}-{case}"
                rows[case], angles[case] = evaluate_case(
                    selected, seed, case, responses, directory,
                    relay_connected=case != "relay-disconnect",
                    silence_motor=case == "vnc-mn-silence", bench_case=bench_case)
                results.append(rows[case])
                (output/"held-out-results.json").write_text(json.dumps(results, indent=2)+"\n")
            checks.extend(pair_checks(seed, rows, angles))
            if any(row["status"] != "completed" for row in rows.values()):
                continue
            for case in ("sham", "reset-replay"):
                checks.append({"seed": seed, "check": case, "passed":
                               rows[case]["physical_sha256"] == rows["intact"]["physical_sha256"]
                               and rows[case]["rate_sha256"] == rows["intact"]["rate_sha256"]})
            for case in ("no-input", "bpn-cut", "dn-silence", "relay-disconnect", "vnc-mn-silence", "motor-disconnect"):
                checks.append({"seed": seed, "check": case,
                               "passed": rows[case]["physical_sha256"] == baseline["physical_sha256"]})
            delta = float(np.max(np.abs(angles["feedback-cut"]-angles["intact"])))
            checks.append({"seed": seed, "check": "feedback removal", "maximum_difference_rad": delta,
                           "passed": delta > .0001 and rows["feedback-cut"]["maximum_local_feedback_torque"] == 0})
        summary = {"status": "passed" if all(item["passed"] for item in checks) else "failed",
                   "candidate": selected, "held_out_checks": checks,
                   "selection_sha256": frozen_hash, "normal_gait_modified": False,
                   "scope": protocol["scope"], "legacy_failed_protocol_preserved": True}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if summary["status"] != "passed":
            raise RuntimeError("Held-out relay checks failed; no refitting performed")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--legacy-packets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.legacy_packets_dir, args.output_dir)
