"""Isolated FlyBody joint probe with an explicitly assumed VNC-rate interface."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from datasets import ROOT
from fly_environment import Environment
from fly_unified import create_environment
from vnc_reference import MOTOR_BODY_ID, DURATION_S, SAMPLE_DT_S, CASES as REFERENCE_CASES


JOINT = "walker/coxa_T1_left"
RECRUITMENT_RATE = 10.
ACTIVATION_TAU_S = .06
TORQUE_SCALE = .002
FEEDBACK_STIFFNESS = .005
FEEDBACK_DAMPING = .00005
MAX_TORQUE = .002
BENCH_RAISE_CM = .5
FIXTURE_TIMECONSTANT_S = .0005
CASES = ("intact", "sham", "dn-cut", "mn-silence", "no-drive", "motor-disconnect",
         "feedback-cut", "reset-replay")
SCOPE = (
    "Measured male MANC connectivity with assumed continuous rate dynamics -> "
    "assumed saturating recruitment/activation and local position/velocity reflex "
    "-> a direct torque probe at one existing FlyBody joint. Thorax is externally "
    "welded for a tethered bench test. Not female-brain spike control, measured "
    "muscle force, reconstructed proprioceptors, fore-aft muscle mapping or walking."
)


def activation_step(activation, rate, duration):
    import math
    if (not all(math.isfinite(value) for value in (activation, rate, duration))
            or not 0 <= activation <= 1 or rate < 0 or duration <= 0):
        raise ValueError("Recruitment requires bounded activation, nonnegative finite rate and positive duration")
    target = rate/(rate+RECRUITMENT_RATE)
    return target+(activation-target)*math.exp(-duration/ACTIVATION_TAU_S)


def torque_command(activation, displacement, velocity, feedback):
    import math
    if (not all(math.isfinite(value) for value in (activation, displacement, velocity))
            or not 0 <= activation <= 1 or type(feedback) is not bool):
        raise ValueError("Joint proxy requires finite physical feedback and bounded activation")
    drive = TORQUE_SCALE*activation
    correction = -FEEDBACK_STIFFNESS*displacement-FEEDBACK_DAMPING*velocity if feedback else 0.
    return max(-MAX_TORQUE, min(MAX_TORQUE, drive+correction)), drive, correction


def physical_rate_trace(rates):
    import numpy as np
    if rates.shape != (1001,) or not np.isfinite(rates).all() or rates.min() < -1e-8:
        raise ValueError("Physical rate trace exceeds the independent reference's finite/negative-roundoff bound")
    diagnostics = {"negative_roundoff_samples": int(np.count_nonzero(rates < 0)),
                   "minimum_raw_rate": float(rates.min()),
                   "policy": "Preserve raw reference; project only accepted numerical negatives in[-1e-8,0) to0at the physical interface"}
    if diagnostics["negative_roundoff_samples"]:
        print(f"WARNING: physical interface projects {diagnostics['negative_roundoff_samples']} "
              f"accepted roundoff samples (minimum={rates.min()})", file=sys.stderr)
    return np.maximum(rates, 0.), diagnostics


def validate_reference_manifest(protocol, validation):
    import math
    variants = protocol.get("variants")
    ids = protocol.get("body_ids")
    motor = protocol.get("motor_index")
    parameter_seed = protocol.get("prospective_parameter_seed")
    if (not isinstance(variants, list) or len(variants) != 3
            or any(not isinstance(value, str) for value in variants) or len(set(variants)) != 3
            or type(parameter_seed) is not int or not 0 <= parameter_seed < 2**32
            or set(variants) != {"saved-336", "saved-422", f"prospective-{parameter_seed}"}
            or not isinstance(ids, list) or len(ids) != 148
            or any(not isinstance(value, str) or not value.isascii() or not value.isdecimal() for value in ids)
            or len(set(ids)) != 148 or type(motor) is not int or not 4 <= motor < 148
            or ids[motor] != MOTOR_BODY_ID):
        raise ValueError("Joint probe requires exact reference variants and motor-body ordering")
    checks = validation.get("checks")
    expected = {(variant, case) for variant in variants
                for case in (*REFERENCE_CASES, "independent-integrator", "tighter-tolerance", "fresh-reset-replay")}
    if (validation.get("status") != "passed" or not isinstance(checks, list)
            or any(not isinstance(check, dict) or check.get("passed") is not True for check in checks)
            or len(checks) != len(expected)
            or {(check.get("variant"), check.get("case")) for check in checks} != expected
            or type(protocol.get("schema_version")) is not int or protocol["schema_version"] != 1
            or protocol.get("reference_kind") != "independent-event-resolved-float64"
            or protocol.get("motor_body_id") != MOTOR_BODY_ID
            or type(protocol.get("duration_s")) not in (float, int) or protocol["duration_s"] != DURATION_S
            or type(protocol.get("sample_dt_s")) not in (float, int) or protocol["sample_dt_s"] != SAMPLE_DT_S):
        raise ValueError("Physical probe requires the complete independently validated exact motor reference")
    for check in checks:
        if check["case"] in {"independent-integrator", "tighter-tolerance"}:
            difference = check.get("maximum_rate_difference")
            if (type(difference) not in (float, int) or not math.isfinite(difference)
                    or not 0 <= difference < .001):
                raise ValueError("Reference convergence result does not meet its declared bound")
        elif check["case"] == "fresh-reset-replay" and check.get("maximum_rate_difference") != 0:
            raise ValueError("Reference replay must have exact zero difference")


def make_bench():
    import mujoco as mj
    import numpy as np

    with create_environment(Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json"), .1) as env:
        env.reset()
        source, initial = env.physics.model.ptr, env.physics.data.ptr
        root_joints = [index for index in range(source.njnt)
                       if source.joint(index).name.startswith("walker/") and source.jnt_type[index] == mj.mjtJoint.mjJNT_FREE]
        if len(root_joints) != 1:
            raise ValueError("Joint bench requires the single FlyBody free root")
        root_qpos = int(source.jnt_qposadr[root_joints[0]])
        initial.qpos[root_qpos+2] += BENCH_RAISE_CM
        mj.mj_forward(source, initial)
        body = source.body("walker/thorax").id
        position, quaternion = np.zeros(3), np.zeros(4)
        mj.mju_negPose(position, quaternion, initial.xpos[body], initial.xquat[body])
        xml = ET.fromstring(env.task.root_entity.mjcf_model.to_xml_string())
        equality = xml.find("equality")
        if equality is None:
            equality = ET.SubElement(xml, "equality")
        ET.SubElement(equality, "weld", name="joint_probe_fixture", body1="walker/thorax",
                      relpose=" ".join(str(value) for value in [*position, *quaternion]),
                      solref=f"{FIXTURE_TIMECONSTANT_S} 1")
        target = next(node for node in xml.find("actuator") if node.get("name") == JOINT)
        target.set("dyntype", "none")
        encoded = ET.tostring(xml, encoding="unicode")
        model = mj.MjModel.from_xml_string(encoded, env.task.root_entity.mjcf_model.get_assets())
        if (not np.array_equal(model.body_mass, source.body_mass)
                or not np.array_equal(model.body_inertia, source.body_inertia)):
            raise RuntimeError("Bench changed FlyBody mass/inertia instead of only the declared fixture/actuation")
        data = mj.MjData(model)
        data.qpos[:] = initial.qpos
        data.qvel[:] = initial.qvel
        model.actuator_gainprm[:] = 0
        model.actuator_biasprm[:] = 0
        actuator = model.actuator(JOINT).id
        model.actuator_gainprm[actuator, 0] = 1.
        model.actuator_ctrlrange[actuator] = [-MAX_TORQUE, MAX_TORQUE]
        model.actuator_forcerange[actuator] = [-MAX_TORQUE, MAX_TORQUE]
        model.actuator_ctrllimited[actuator] = 1
        model.actuator_forcelimited[actuator] = 1
        mj.mj_forward(model, data)
        metadata = {"fixture_xml_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                    "target_joint_axis": model.jnt_axis[model.joint(JOINT).id].tolist(),
                    "timestep_s": float(model.opt.timestep),
                    "original_mass_inertia_preserved": True, "all_other_actuator_gains_biases_zero": True}
        return model, data, actuator, metadata


def trial(rates, case, directory):
    import mujoco as mj
    import numpy as np

    if case not in CASES or rates.shape != (1001,) or not np.isfinite(rates).all() or (rates < 0).any():
        raise ValueError("Joint probe requires a declared case and exact one-second nonnegative rate trace")
    model, data, actuator, metadata = make_bench()
    joint = model.joint(JOINT).id
    qpos, qvel = int(model.jnt_qposadr[joint]), int(model.jnt_dofadr[joint])
    initial = float(data.qpos[qpos])
    body = model.body("walker/thorax").id
    initial_body = data.xpos[body].copy()
    duration = float(model.opt.timestep)
    steps = round(DURATION_S/duration)
    if abs(steps*duration-DURATION_S) > 1e-9:
        raise ValueError("Bench needs an exact one-second physical timestep budget")
    activation = 0.
    activation_integral = 0.
    digest = hashlib.sha256()
    rows = []
    maximum_fixture_drift = 0.
    with (directory/"intervals.jsonl").open("x") as log:
        for step in range(steps):
            elapsed = step*duration
            rate_index = min(1000, int((elapsed+1e-12)/SAMPLE_DT_S))
            rate = float(rates[rate_index])
            delivered = 0. if case == "motor-disconnect" else rate
            activation = activation_step(activation, delivered, duration)
            activation_integral += activation*duration
            command, drive, correction = torque_command(
                activation, float(data.qpos[qpos])-initial, float(data.qvel[qvel]), case != "feedback-cut")
            data.ctrl[actuator] = command
            mj.mj_step(model, data)
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise RuntimeError("Joint bench produced non-finite physics")
            if data.xfrc_applied.any() or data.qfrc_applied.any():
                raise RuntimeError("Joint bench unexpectedly used external applied body/joint forces")
            if abs(float(data.actuator_force[actuator])-command) > 1e-10:
                raise RuntimeError("Target torque transmission does not match the declared actuator command")
            digest.update(data.qpos.tobytes())
            digest.update(data.qvel.tobytes())
            digest.update(data.ctrl.tobytes())
            digest.update(data.actuator_force.tobytes())
            maximum_fixture_drift = max(maximum_fixture_drift, float(np.linalg.norm(data.xpos[body]-initial_body)))
            if (step+1) % round(SAMPLE_DT_S/duration) == 0:
                row = {"end_s": (step+1)*duration, "source_rate": rate, "delivered_rate": delivered,
                       "activation": activation, "joint_rad": float(data.qpos[qpos]),
                       "velocity_rad_s": float(data.qvel[qvel]), "command": command,
                       "feedforward_torque": drive, "local_feedback_torque": correction,
                       "actuator_torque": float(data.actuator_force[actuator])}
                rows.append(row)
                log.write(json.dumps(row)+"\n")
    if abs(data.time-DURATION_S) > 1e-8:
        raise RuntimeError("Joint reference/physical duration disagree")
    summary = {"case": case, "physical_sha256": digest.hexdigest(),
               "maximum_fixture_drift_cm": maximum_fixture_drift,
               "maximum_joint_rad": max(row["joint_rad"] for row in rows),
               "minimum_joint_rad": min(row["joint_rad"] for row in rows),
               "joint_limits_rad": model.jnt_range[joint].tolist(),
               "maximum_activation": max(row["activation"] for row in rows),
               "activation_integral_s": activation_integral,
               "maximum_torque": max(abs(row["command"]) for row in rows),
               "maximum_local_feedback_torque": max(abs(row["local_feedback_torque"]) for row in rows),
               "final_joint_rad": rows[-1]["joint_rad"], "metadata": metadata,
               "scope": SCOPE}
    (directory/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    return summary, np.array([row["joint_rad"] for row in rows])


def run(reference, output):
    import numpy as np

    reference, output = reference.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (reference, output)) or output.exists():
        raise ValueError("Use a verified external reference and a new external joint-test directory")
    protocol = json.loads((reference/"protocol.json").read_text())
    validation = json.loads((reference/"summary.json").read_text())
    validate_reference_manifest(protocol, validation)
    recorded = {(row["variant"], row["case"]): row["rate_sha256"]
                for row in json.loads((reference/"results.json").read_text())}
    output.mkdir(parents=True)
    physical_protocol = {
        "scope": SCOPE, "joint": JOINT, "motor_body_id": MOTOR_BODY_ID, "cases": CASES,
        "variants": protocol["variants"], "reference_code_sha256": protocol["code_sha256"],
        "units": {"position": "cm", "angle": "rad", "velocity": "rad/s", "torque": "g*cm^2/s^2"},
        "assumptions": {"recruitment_half_rate": RECRUITMENT_RATE, "activation_tau_s": ACTIVATION_TAU_S,
                        "torque_scale_g_cm2_per_s2": TORQUE_SCALE, "feedback_stiffness": FEEDBACK_STIFFNESS,
                        "feedback_damping": FEEDBACK_DAMPING, "maximum_torque": MAX_TORQUE,
                        "bench_raise_cm": BENCH_RAISE_CM,
                        "fixture_timeconstant_s": FIXTURE_TIMECONSTANT_S,
                        "negative_roundoff_bound": 1e-8},
        "predeclared_checks": [
            "Intact joint differs from no-input by>0.001rad and recruits positive activation.",
            "Sham/reset exact qpos/qvel/control/force hashes.",
            "DNcut/MNsilence/motor-disconnect physics exactly equals no-input.",
            "Feedback removal causes>0.0001rad paired difference and feedback torque stays0.",
            "Fixture drift<0.01cm, torque<=0.002 and joint remains within source limits+0.02rad.",
        ],
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output/"protocol.json").write_text(json.dumps(physical_protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    checks, results = [], []
    try:
        for variant in protocol["variants"]:
            summaries, angles = {}, {}
            for case in CASES:
                source_case = case if case in {"dn-cut", "mn-silence", "no-drive"} else "intact"
                with np.load(reference/f"{variant}-{source_case}.npz", allow_pickle=False) as packet:
                    rates = packet["rates"]
                    expected_times = np.arange(1001)*SAMPLE_DT_S
                    if (rates.shape != (148, 1001) or not np.isfinite(rates).all()
                            or not np.array_equal(packet["time_s"], expected_times)
                            or hashlib.sha256(rates.tobytes()).hexdigest() != recorded[variant, source_case]):
                        raise ValueError("Reference time grid or rate hash changed after validation")
                    signal, rate_diagnostics = physical_rate_trace(rates[protocol["motor_index"]].copy())
                directory = output/f"{variant}-{case}"
                directory.mkdir()
                summaries[case], angles[case] = trial(signal, case, directory)
                summaries[case]["source_rate_diagnostics"] = rate_diagnostics
                (directory/"summary.json").write_text(json.dumps(summaries[case], indent=2)+"\n")
                results.append({"variant": variant, **summaries[case]})
                (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                print(variant, case, summaries[case]["final_joint_rad"], flush=True)
            intact, baseline = summaries["intact"], summaries["no-drive"]
            checks.append({"variant": variant, "check": "motor response",
                           "maximum_difference_rad": float(np.max(np.abs(angles["intact"]-angles["no-drive"]))),
                           "passed": bool(np.max(np.abs(angles["intact"]-angles["no-drive"])) > .001
                                          and intact["maximum_activation"] > 0)})
            for case in ("sham", "reset-replay"):
                checks.append({"variant": variant, "check": case,
                               "passed": summaries[case]["physical_sha256"] == intact["physical_sha256"]})
            for case in ("dn-cut", "mn-silence", "motor-disconnect"):
                checks.append({"variant": variant, "check": case,
                               "passed": summaries[case]["physical_sha256"] == baseline["physical_sha256"]})
            difference = float(np.max(np.abs(angles["feedback-cut"]-angles["intact"])))
            checks.append({"variant": variant, "check": "local feedback removal",
                           "maximum_difference_rad": difference,
                           "passed": difference > .0001 and summaries["feedback-cut"]["maximum_local_feedback_torque"] == 0})
            checks.append({"variant": variant, "check": "physical bounds",
                           "passed": all(row["maximum_fixture_drift_cm"] < .01
                                         and row["maximum_torque"] <= MAX_TORQUE
                                         and row["minimum_joint_rad"] >= row["joint_limits_rad"][0]-.02
                                         and row["maximum_joint_rad"] <= row["joint_limits_rad"][1]+.02
                                         for row in summaries.values())})
        summary = {"status": "passed" if all(row["passed"] for row in checks) else "failed",
                   "checks": checks, "scope": SCOPE, "normal_gait_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if summary["status"] != "passed":
            raise RuntimeError("Assumed joint-interface checks failed; results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    run(args.reference_dir, args.output_dir)
