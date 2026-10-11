"""Physical looming -> actual DNp10 -> reduced actuator pathway causal experiment."""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_environment import Environment
from fly_feeding import BrainClient
from fly_flight import prepare_data
from fly_leg_extension import LegExtension, DNP10_IDS, SCOPE
from fly_looming import SphereLooming, SphereVision, finger_visibility, graded_visual_rates
from fly_policy import PublishedMotorPolicy, prepare_policy
from fly_unified import CONTROL_DT, MotorAdapter, create_environment
from fly_walking import external_output


PROTOCOLS = (
    {"name": "reference", "x_cm": 4.0, "radius_cm": .15, "y_cm": 0.0, "withdraw_s": .18},
    {"name": "held-out", "x_cm": 4.5, "radius_cm": .18, "y_cm": .12, "withdraw_s": .20},
)
CASES = ("intact", "sham", "visual-disconnect", "dn-silence", "motor-disconnect",
         "no-input", "receding", "reset-replay")
DURATION_S = .7
FEEDBACK_PROBE = {"start_s": .26, "withdraw_s": .4, "x_cm": 12., "radius_cm": .3}


def trial(brain, data_dir, paths, policy, protocol, case, directory,
          graded_vision=False, replay_rates=None):
    import mujoco as mj
    import numpy as np

    habitat = replace(Environment.load(ROOT/"experiments/fly-walking/planted-habitat.json"),
                      half_size_mm=300)
    brain.reset()
    decoder = LegExtension(brain.metadata)
    with create_environment(habitat, .8, airborne=True,
                            wing_pattern=paths["wing_pattern_fmech.npy"], interactive=True) as env:
        timestep = env.reset()
        adapter = MotorAdapter(env)
        model, data = env.physics.model.ptr, env.physics.data.ptr
        body = model.body("walker/thorax").id
        sphere = model.geom("virtual_finger_tip").id
        mocap = model.body_mocapid[model.body("virtual_finger").id]
        model.geom_size[sphere, 0] = protocol["radius_cm"]
        ground = model.geom("groundplane").id
        eye_ids = [model.camera(f"walker/eye_{side}").id for side in ("left", "right")]
        looming = {eye: SphereLooming() for eye in eye_ids}
        vision = SphereVision() if graded_vision else None
        if replay_rates is not None and (not graded_vision or len(replay_rates) != 70):
            raise ValueError("Feedback replay requires an exact 70-interval graded rate trace")
        tibias = [model.joint(f"walker/tibia_T1_{side}").qposadr[0] for side in ("left", "right")]
        tibia_actuators = [model.actuator(f"walker/tibia_T1_{side}").id for side in ("left", "right")]
        tips = [model.body(f"walker/claw_T1_{side}").id for side in ("left", "right")]
        physical = hashlib.sha256()
        neural = hashlib.sha256()
        rows = []
        floor_steps = 0
        sphere_contact_steps = 0
        min_upright = 1.0
        first_dn = None
        first_motor = None
        actuator_impulse = np.zeros(2)
        initial_mass, initial_inertia = model.body_mass.copy(), model.body_inertia.copy()
        with (directory/"intervals.jsonl").open("x") as log:
            for interval in range(70):
                start = interval * .01
                feedback_probe = FEEDBACK_PROBE["start_s"] <= start < FEEDBACK_PROBE["withdraw_s"]
                enabled = case != "no-input" and (start < protocol["withdraw_s"] or feedback_probe)
                position = np.array([protocol["x_cm"], protocol["y_cm"], 1.05])
                radius = protocol["radius_cm"]
                if feedback_probe:
                    position[0] = FEEDBACK_PROBE["x_cm"]
                    radius = FEEDBACK_PROBE["radius_cm"]
                if case == "receding":
                    position[0] += 40 * start
                model.geom_size[sphere, 0] = radius
                data.mocap_pos[mocap] = position if enabled else [0, 0, -10]
                mj.mj_forward(model, data)
                rates = None
                geometric_rates = None
                if vision is not None:
                    features = vision.sample(model, data, [
                        {"geom_id": sphere, "name": "stimulus_sphere", "enabled": enabled}],
                        eye_ids, body, .01)
                    geometric_rates = graded_visual_rates(features)
                    rates = dict(geometric_rates)
                    if case == "feedback-cut" and feedback_probe:
                        rates = {"LC4": 0., "LPLC2": 0.}
                    if replay_rates is not None:
                        rates = dict(replay_rates[interval])
                    stimulus = any(rates.values())
                else:
                    views = finger_visibility(model, data, sphere, position, radius, eye_ids, body)
                    features = [looming[v["camera_id"]].sample(
                        v["distance_mm"]*10, radius*10, .01, enabled, v["visible"])
                        for v in views]
                    stimulus = any(feature["looming_active"] for feature in features)
                brain.begin_step(10, False, stimulus, visual_rates_Hz=rates)
                response = brain.finish_step()
                for _ in range(50):
                    motor, _ = policy.action(adapter.flight_observation(timestep.observation),
                                             adapter.projections["flight"]["spec"])
                    activation = decoder.advance(CONTROL_DT, True)
                    applied = 0.0 if case == "motor-disconnect" else activation
                    action = adapter.leg_extension_action(adapter.flight_action(motor), applied)
                    if applied > 0 and first_motor is None:
                        first_motor = float(env.physics.time())
                    timestep = env.step(action)
                    if timestep.last() or not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                        raise RuntimeError("Extension trial terminated or produced invalid physics")
                    physical.update(data.qpos.tobytes())
                    physical.update(data.qvel.tobytes())
                    physical.update(action.tobytes())
                    actuator_impulse += np.abs(data.actuator_force[tibia_actuators]) * CONTROL_DT
                    floor_steps += int(any(c.geom1 == ground or c.geom2 == ground
                                           for c in data.contact[:data.ncon]))
                    sphere_contact_steps += int(any(c.geom1 == sphere or c.geom2 == sphere
                                                    for c in data.contact[:data.ncon]))
                    min_upright = min(min_upright, float(data.xmat[body].reshape(3, 3)[2, 2]))
                counts = response["sensorimotor_spikes"]
                dn_count = sum(counts[value] for value in DNP10_IDS.values())
                if dn_count and first_dn is None:
                    first_dn = response["brain_time_ms"] / 1000
                if abs(response["brain_time_ms"] - env.physics.time()*1000) > 1e-5:
                    raise RuntimeError("Extension brain/body clocks diverged")
                decoder.accept(response)
                if data.xfrc_applied.any():
                    raise RuntimeError("Extension trial unexpectedly applied external body assistance")
                sparse = response["neuron_activity"]
                neural.update(json.dumps([sparse["indices"], sparse["counts"]]).encode())
                rotation = data.xmat[body].reshape(3, 3)
                tip_x = [float(((data.xpos[tip]-data.xpos[body]) @ rotation)[0])*10 for tip in tips]
                row = {"end_s": (interval+1)*.01, "stimulus": stimulus, "looming": features,
                       **({"geometric_visual_rates_Hz": geometric_rates,
                           "applied_visual_rates_Hz": rates} if graded_vision else {}),
                       "feedback_probe": feedback_probe, "sphere_position_cm": position.tolist(),
                       "sphere_radius_cm": radius, "sphere_enabled": enabled,
                       "response": response, "extension": decoder.snapshot(),
                       "front_tibia_rad": data.qpos[tibias].tolist(),
                       "front_tibia_actuator_force": data.actuator_force[tibia_actuators].tolist(),
                       "front_tibia_absolute_force_integral": actuator_impulse.tolist(),
                       "front_tip_forward_mm": tip_x, "position_cm": data.xpos[body].tolist()}
                log.write(json.dumps(row)+"\n")
                rows.append(row)
        if not np.array_equal(initial_mass, model.body_mass) or not np.array_equal(initial_inertia, model.body_inertia):
            raise RuntimeError("Extension trial changed body mass or inertia")
        result = {
            "case": case, "protocol": protocol["name"], "dn_spikes": decoder.total_spikes,
            "stimulus_intervals": sum(row["stimulus"] for row in rows),
            "network_spikes": sum(row["response"]["network_spikes"] for row in rows),
            "first_dn_delivery_s": first_dn, "first_motor_s": first_motor,
            "peak_activation": max(row["extension"]["activation"] for row in rows),
            "final_activation": decoder.activation,
            "floor_contact_steps": floor_steps, "minimum_upright_cosine": min_upright,
            "sphere_contact_steps": sphere_contact_steps,
            "physical_sha256": physical.hexdigest(), "neural_sha256": neural.hexdigest(),
            "external_assistance": False, "physical_state_resets_during_trial": 0,
            "front_tibia_absolute_force_integral": actuator_impulse.tolist(),
            "actuator_force_units": "FlyBody native generalized force; not biological muscle force",
        }
        (directory/"summary.json").write_text(json.dumps(result, indent=2)+"\n")
        return result, rows


def evaluate(results, rows):
    import numpy as np

    checks = {}
    for protocol in PROTOCOLS:
        name = protocol["name"]
        group = {case: results[(name, case)] for case in CASES}
        reference = group["intact"]
        checks[f"{name}:intact-response"] = reference["dn_spikes"] > 0 and reference["first_motor_s"] is not None
        for case in ("sham", "reset-replay"):
            checks[f"{name}:{case}-exact"] = all(
                reference[field] == group[case][field] for field in ("neural_sha256", "physical_sha256"))
        for case in ("visual-disconnect", "dn-silence", "no-input", "receding"):
            checks[f"{name}:{case}-no-recruitment"] = (
                group[case]["dn_spikes"] == 0 and group[case]["peak_activation"] == 0)
        checks[f"{name}:visual-source-retained"] = group["visual-disconnect"]["network_spikes"] > 0
        checks[f"{name}:motor-disconnect-neural-response"] = group["motor-disconnect"]["dn_spikes"] > 0
        checks[f"{name}:motor-intervention-physics"] = (
            group["motor-disconnect"]["physical_sha256"] == group["dn-silence"]["physical_sha256"])
        intact_rows, base_rows = rows[(name, "intact")], rows[(name, "motor-disconnect")]
        joint = np.array([r["front_tibia_rad"] for r in intact_rows]) - np.array(
            [r["front_tibia_rad"] for r in base_rows])
        tips = np.array([r["front_tip_forward_mm"] for r in intact_rows]) - np.array(
            [r["front_tip_forward_mm"] for r in base_rows])
        reference["peak_mean_front_tibia_delta_rad"] = float(joint.mean(axis=1).max())
        reference["peak_mean_front_tip_delta_mm"] = float(tips.mean(axis=1).max())
        reference["final_mean_front_tibia_delta_rad"] = float(joint[-1].mean())
        reference["actuator_force_integral_difference"] = float(np.max(np.abs(
            np.array(reference["front_tibia_absolute_force_integral"])
            - np.array(group["motor-disconnect"]["front_tibia_absolute_force_integral"]))))
        angles = np.array([[f["angular_size_rad"] for f in r["looming"]] for r in intact_rows])
        base_angles = np.array([[f["angular_size_rad"] for f in r["looming"]] for r in base_rows])
        visible = np.array([[f["visible"] for f in r["looming"]] for r in intact_rows])
        base_visible = np.array([[f["visible"] for f in r["looming"]] for r in base_rows])
        reference["sensory_feedback_angular_difference_rad"] = float(
            np.max(np.abs(angles-base_angles)[visible & base_visible], initial=0))
        reference["physical_extension_onset_s"] = next(
            (r["end_s"] for r, delta in zip(intact_rows, joint.mean(axis=1)) if delta >= .01), None)
        checks[f"{name}:physical-extension"] = (
            reference["peak_mean_front_tibia_delta_rad"] >= .15
            and reference["peak_mean_front_tip_delta_mm"] >= .1)
        checks[f"{name}:actuator-force-changed"] = reference["actuator_force_integral_difference"] > 1e-9
        checks[f"{name}:physics-to-sensory-feedback"] = reference["sensory_feedback_angular_difference_rad"] > 1e-9
        checks[f"{name}:feedback-probe-drives-brain"] = any(
            r["feedback_probe"] and r["stimulus"] and r["response"]["network_spikes"] > 0 for r in intact_rows)
        checks[f"{name}:withdrawal-decay"] = reference["final_activation"] <= .1 * reference["peak_activation"]
        checks[f"{name}:no-retrocausal-actuation"] = (
            reference["first_motor_s"] is not None and reference["first_dn_delivery_s"] is not None
            and reference["first_motor_s"] >= reference["first_dn_delivery_s"] - 1e-9)
        checks[f"{name}:airborne-valid-physics"] = all(
            r["floor_contact_steps"] == 0 and r["sphere_contact_steps"] == 0
            and r["minimum_upright_cosine"] > .4 for r in group.values())
    return checks


def run(data_dir, output, seeds=(420, 421)):
    output = external_output(output)
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or s < 0 for s in seeds):
        raise ValueError("Use distinct nonnegative seeds")
    output.mkdir(parents=True)
    protocol = {"scope": SCOPE, "stimuli": PROTOCOLS, "seeds": seeds, "cases": CASES,
                "duration_s": DURATION_S, "feedback_probe": FEEDBACK_PROBE,
                "neural_interval_ms": 10, "initialization": "explicit airborne diagnostic",
                "thresholds": {"front_tibia_delta_rad": .15, "front_tip_forward_delta_mm": .1,
                               "minimum_upright_cosine": .4, "floor_contact_steps": 0,
                               "final_activation_fraction": .1},
                "held_out": "No decoder parameter fitting. Seed 422 is reserved for prospective validation; earlier single-pulse seed-421 failures remain preserved.",
                "source_sha256": {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                                  for name in ("fly_leg_extension.py", "fly_brain_worker.py", "fly_unified.py",
                                               "test_leg_extension_causality.py", "fly_looming.py")}}
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        paths = prepare_data(data_dir)
        policy = PublishedMotorPolicy(prepare_policy(data_dir, CATALOG, "flight"))
        reports = []
        for seed in seeds:
            results, traces = {}, {}
            for intervention, selected_cases in (
                (None, ("intact", "motor-disconnect", "no-input", "receding", "reset-replay")),
                ("sham", ("sham",)), ("visual-disconnect", ("visual-disconnect",)),
                ("silence", ("dn-silence",)),
            ):
                worker_dir = output/f"seed-{seed}-worker-{intervention or 'intact'}"
                worker_dir.mkdir()
                brain = BrainClient(
                    ROOT/".venv/bin/python", data_dir, worker_dir, seed, takeoff=True, telemetry=True,
                    disconnect_visual_output="both" if intervention == "visual-disconnect" else None,
                    dnp10_intervention=intervention if intervention in {"sham", "silence"} else None)
                try:
                    (worker_dir/"metadata.json").write_text(json.dumps(brain.metadata)+"\n")
                    for stimulus in PROTOCOLS:
                        for case in selected_cases:
                            directory = output/f"seed-{seed}-{stimulus['name']}-{case}"
                            directory.mkdir()
                            result, trace = trial(brain, data_dir, paths, policy, stimulus, case, directory)
                            key = (stimulus["name"], case)
                            results[key], traces[key] = result, trace
                            print(f"seed={seed} {key}: DN={result['dn_spikes']} "
                                  f"activation={result['peak_activation']:.3f}", flush=True)
                finally:
                    brain.close()
            checks = evaluate(results, traces)
            report = {"seed": seed, "checks": checks, "results": list(results.values())}
            reports.append(report)
            (output/"results.json").write_text(json.dumps(reports, indent=2)+"\n")
            if not all(checks.values()):
                raise RuntimeError(f"Predeclared extension checks failed: {[k for k,v in checks.items() if not v]}")
        (output/"status.json").write_text('{"status":"passed"}\n')
        return reports
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[420, 421])
    args = parser.parse_args()
    try:
        run(args.data_dir, args.output_dir, tuple(args.seeds))
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(1, f"ERROR: extension causal experiment failed: {error}\n")


if __name__ == "__main__":
    main()
