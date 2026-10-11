"""Causal graded sensory -> actual network -> reduced leg actuation -> sensory feedback."""

import argparse
import hashlib
import json
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_feeding import BrainClient
from fly_flight import prepare_data
from fly_looming import GRADED_ENCODER
from fly_policy import PublishedMotorPolicy, prepare_policy
from fly_walking import external_output
from test_leg_extension_causality import PROTOCOLS, FEEDBACK_PROBE, trial, evaluate


CASES = ("intact", "sham", "visual-disconnect", "dn-silence", "motor-disconnect",
         "no-input", "receding", "reset-replay", "feedback-cut", "feedback-sham",
         "feedback-clamped")


def verify_sources(hashes):
    changed = [name for name, digest in hashes.items()
               if hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest() != digest]
    if changed:
        raise RuntimeError(f"Source files changed during causal assay: {changed}")


def feedback_checks(results, traces):
    checks = evaluate(results, traces)
    for protocol in PROTOCOLS:
        name = protocol["name"]
        reference = results[(name, "intact")]
        for case in ("feedback-sham",):
            checks[f"{name}:{case}-exact"] = all(
                reference[field] == results[(name, case)][field]
                for field in ("neural_sha256", "physical_sha256"))
        intact, disconnected = traces[(name, "intact")], traces[(name, "motor-disconnect")]
        difference = max(abs(a["geometric_visual_rates_Hz"][population]
                             - b["geometric_visual_rates_Hz"][population])
                         for a, b in zip(intact, disconnected) for population in ("LC4", "LPLC2"))
        reference["peak_motor_dependent_rate_difference_Hz"] = difference
        checks[f"{name}:motor-to-graded-input-feedback"] = difference > 1e-9
        cut = traces[(name, "feedback-cut")]
        before = lambda rows: [r for r in rows if r["end_s"] <= FEEDBACK_PROBE["start_s"]]
        checks[f"{name}:feedback-cut-preserves-initial-chain"] = all(
            a["response"]["neuron_activity"]["indices"] == b["response"]["neuron_activity"]["indices"]
            and a["response"]["neuron_activity"]["counts"] == b["response"]["neuron_activity"]["counts"]
            and a["front_tibia_rad"] == b["front_tibia_rad"]
            for a, b in zip(before(intact), before(cut)))
        checks[f"{name}:feedback-cut-zeroes-only-second-presentation"] = all(
            (not r["feedback_probe"] or not any(r["applied_visual_rates_Hz"].values())) for r in cut)
        feedback_spikes = lambda rows: sum(r["response"]["network_spikes"] for r in rows
                                          if r["feedback_probe"])
        reference["feedback_network_spikes"] = feedback_spikes(intact)
        reference["feedback_cut_network_spikes"] = feedback_spikes(cut)
        checks[f"{name}:feedback-input-changes-real-network"] = (
            reference["feedback_network_spikes"] > reference["feedback_cut_network_spikes"])
        motor_difference = max(abs(sum(a-b for a,b in zip(r["front_tibia_rad"], c["front_tibia_rad"]))/2)
                               for r,c in zip(intact, cut) if r["end_s"] > FEEDBACK_PROBE["start_s"])
        reference["feedback_cut_peak_front_tibia_difference_rad"] = motor_difference
        checks[f"{name}:feedback-input-changes-dn-and-physical-response"] = (
            reference["dn_spikes"] > results[(name, "feedback-cut")]["dn_spikes"]
            and motor_difference >= .01)
        clamped = results[(name, "feedback-clamped")]
        reference["feedback_clamp_changed_neural_hash"] = reference["neural_sha256"] != clamped["neural_sha256"]
        reference["feedback_clamp_changed_physical_hash"] = reference["physical_sha256"] != clamped["physical_sha256"]
        checks[f"{name}:feedback-clamp-replays-control-rates-exactly"] = all(
            a["applied_visual_rates_Hz"] == b["applied_visual_rates_Hz"]
            for a, b in zip(traces[(name, "feedback-clamped")], disconnected))
        checks[f"{name}:all-feedback-interventions-have-valid-airborne-physics"] = all(
            result["floor_contact_steps"] == 0 and result["sphere_contact_steps"] == 0
            and result["minimum_upright_cosine"] > .4
            for (geometry, _), result in results.items() if geometry == name)
    return checks


def run(data_dir, output, seeds=(420, 423)):
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or s < 0 for s in seeds):
        raise ValueError("Use distinct nonnegative neural seeds")
    output = external_output(output)
    output.mkdir(parents=True)
    protocol = {"encoder": GRADED_ENCODER, "stimuli": PROTOCOLS, "feedback_probe": FEEDBACK_PROBE,
                "seeds": seeds, "cases": CASES, "physical_initialization": "airborne diagnostic; wing phase 0.5",
                "scope": "Assumed graded vision and reduced VNC/actuation, actual chemical-network spikes and physics. No calibrated biology or feedback stabilization claim.",
                "thresholds": {"front_tibia_delta_rad": .15, "front_claw_delta_mm": .1,
                               "motor_dependent_rate_delta_Hz": 1e-9,
                               "feedback_cut_front_tibia_delta_rad": .01},
                "predeclared_feedback_tests": [
                    "Motor intervention changes physical eye geometry and continuously encoded rates",
                    "Exact intact rate replay is sham; motor-control rate replay severs motor-dependent sensory feedback",
                    "Cutting only the second sensory presentation preserves the initial chain and reduces real feedback-interval network response",
                    "Report whether motor-dependent rate replay changes actual spikes/physics; do not force success for sub-resolution stochastic effects"],
                "source_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                                  for name in ("fly_looming.py", "fly_brain_worker.py", "fly_feeding.py",
                                               "test_leg_extension_causality.py", "test_graded_visual_feedback.py",
                                               "fly_leg_extension.py", "fly_unified.py")}}
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        paths = prepare_data(data_dir)
        policy = PublishedMotorPolicy(prepare_policy(data_dir, CATALOG, "flight"))
        reports = []
        for seed in seeds:
            results, traces = {}, {}
            for intervention, cases in (
                (None, ("intact", "motor-disconnect", "no-input", "receding", "reset-replay",
                        "feedback-cut", "feedback-sham", "feedback-clamped")),
                ("sham", ("sham",)), ("visual-disconnect", ("visual-disconnect",)),
                ("silence", ("dn-silence",)),
            ):
                worker_dir = output/f"seed-{seed}-worker-{intervention or 'intact'}"
                verify_sources(protocol["source_sha256"])
                worker_dir.mkdir()
                brain = BrainClient(ROOT/".venv/bin/python", data_dir, worker_dir, seed,
                                    takeoff=True, telemetry=True, graded_vision=True,
                                    disconnect_visual_output="both" if intervention == "visual-disconnect" else None,
                                    dnp10_intervention=intervention if intervention in {"sham", "silence"} else None)
                try:
                    (worker_dir/"metadata.json").write_text(json.dumps(brain.metadata)+"\n")
                    for stimulus in PROTOCOLS:
                        for case in cases:
                            directory = output/f"seed-{seed}-{stimulus['name']}-{case}"
                            directory.mkdir()
                            replay = None
                            if case in {"feedback-sham", "feedback-clamped"}:
                                source_case = "intact" if case == "feedback-sham" else "motor-disconnect"
                                replay = [r["applied_visual_rates_Hz"] for r in traces[(stimulus["name"], source_case)]]
                            result, trace = trial(brain, data_dir, paths, policy, stimulus, case, directory,
                                                  graded_vision=True, replay_rates=replay)
                            key = (stimulus["name"], case)
                            results[key], traces[key] = result, trace
                            print(f"seed={seed} {key}: DN={result['dn_spikes']} "
                                  f"activation={result['peak_activation']:.3f}", flush=True)
                finally:
                    brain.close()
                verify_sources(protocol["source_sha256"])
            checks = feedback_checks(results, traces)
            reports.append({"seed": seed, "checks": checks, "results": list(results.values())})
            (output/"results.json").write_text(json.dumps(reports, indent=2)+"\n")
            if not all(checks.values()):
                raise RuntimeError(f"Predeclared feedback checks failed: {[k for k,v in checks.items() if not v]}")
        verify_sources(protocol["source_sha256"])
        (output/"status.json").write_text('{"status":"passed","source_hashes_unchanged":true}\n')
        return reports
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[420, 423])
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir, tuple(args.seeds))
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(1, f"ERROR: graded visual feedback assay failed: {error}\n")


if __name__ == "__main__":
    main()
