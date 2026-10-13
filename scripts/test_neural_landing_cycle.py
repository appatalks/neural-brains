"""Actual visual network response -> DNp10 request -> physical reduced landing cycle."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from datasets import ROOT,CATALOG
from fly_environment import Environment
from fly_feeding import BrainClient
from fly_flight import prepare_data
from fly_flight_arena import FlyContactReader
from fly_neural_landing import NeuralLanding,SCOPE
from fly_policy import PublishedMotorPolicy,prepare_tflite_policy
from fly_unified import CONTROL_DT,WALK_EVERY,MotorAdapter,create_environment
from fly_looming import SphereVision
from fly_walking import external_output
from sim_units import simulation_steps


def run(data_dir,output,seconds=4.5,seed=420,case="intact",phase=.5):
    import numpy as np
    import mujoco as mj

    steps=simulation_steps(seconds,CONTROL_DT)
    if (not .5<=seconds<=8 or type(seed) is not int or seed<0
        or case not in {"intact","sham","silence","visual-disconnect","no-input"}
        or not math.isfinite(phase) or not 0<=phase<1):
        raise ValueError("Use bounded duration, explicit case, nonnegative seed and wing phase in [0,1)")
    output=external_output(output)
    output.mkdir(parents=True)
    (output/"protocol.json").write_text(json.dumps({
        "scope":SCOPE,"seconds":seconds,"seed":seed,"case":case,"wing_phase":phase,
        "visual_stimulus":"Explicit stationary visible sphere approached by the physical airborne body, 100Hz existing approximate LC4/LPLC2 gate; not fitted natural landing input",
        "thresholds":{"stable_unassisted_walking_steps":1500,"upright":.8,"post_release_forward_mm":1.},
        "source_sha256":{name:hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                         for name in ("fly_neural_landing.py","fly_walking_navigation.py","fly_unified.py",
                                      "fly_brain_worker.py","test_neural_landing_cycle.py")},
    },indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        paths=prepare_data(data_dir)
        walking=PublishedMotorPolicy(prepare_tflite_policy(data_dir,CATALOG,"walking"))
        flying=PublishedMotorPolicy(prepare_tflite_policy(data_dir,CATALOG,"flight"))
        brain=BrainClient(ROOT/".venv/bin/python",data_dir,output,seed,takeoff=True,telemetry=True,
                          dnp10_intervention="silence" if case=="silence" else "sham" if case=="sham" else None,
                          disconnect_visual_output="both" if case=="visual-disconnect" else None)
        try:
            (output/"brain-metadata.json").write_text(json.dumps(brain.metadata)+"\n")
            landing=NeuralLanding(brain.metadata)
            habitat=Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json")
            with create_environment(habitat,seconds+.1,airborne=True,
                                    wing_pattern=paths["wing_pattern_fmech.npy"],interactive=True,
                                    initial_wing_phase=phase) as env:
                timestep=env.reset()
                adapter=MotorAdapter(env)
                model,data=env.physics.model.ptr,env.physics.data.ptr
                body=model.body("walker/thorax").id
                contacts=FlyContactReader(model,habitat)
                geom=model.geom("virtual_finger_tip").id
                mocap=model.body_mocapid[model.body("virtual_finger").id]
                eyes=[model.camera("walker/eye_"+side).id for side in ("left","right")]
                vision=SphereVision()
                walking_motor=None
                released_position=None
                minimum_boundary=habitat.half_size_mm*.1
                physical=hashlib.sha256()
                network_spikes=0
                before_model_mass=model.body_mass.copy()
                before_model_inertia=model.body_inertia.copy()
                handoffs=[]
                with (output/"trajectory.jsonl").open("x") as log:
                    for interval in range(round(seconds/.01)):
                        elapsed=interval*.01
                        enabled=case!="no-input" and elapsed<.18
                        data.mocap_pos[mocap]=[4,0,1.05] if enabled else [0,0,-10]
                        mj.mj_forward(model,data)
                        features=vision.sample(model,data,[{"geom_id":geom,"name":"looming_sphere","enabled":enabled}],
                                               eyes,body,.01)
                        stimulus=any(f["looming_active"] for f in features)
                        brain.begin_step(10,False,stimulus)
                        response=brain.finish_step()
                        network_spikes+=response["network_spikes"]
                        for tick in range(50):
                            t=env.physics.time()
                            data.xfrc_applied[body]=0.
                            landing.decoder.advance(CONTROL_DT,landing.request_time is None)
                            if landing.request_time is None:
                                motor,_=flying.action(adapter.flight_observation(timestep.observation),
                                                      adapter.projections["flight"]["spec"])
                                action=adapter.flight_action(motor)
                            else:
                                action,walking_motor=landing.motor_action(
                                    adapter,walking,flying,timestep.observation,t,
                                    None if tick%WALK_EVERY==0 else walking_motor)
                                velocity=np.zeros(6)
                                mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                                data.xfrc_applied[body]=landing.assistance(
                                    sum(model.body_mass[i] for i in range(model.nbody)
                                        if (mj.mj_id2name(model,mj.mjtObj.mjOBJ_BODY,i) or "").startswith("walker")),
                                    t,data.xpos[body],velocity,data.xmat[body].reshape(3,3))
                            timestep=env.step(action.copy())
                            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all() or timestep.last():
                                raise RuntimeError("Neural landing trial produced invalid or terminated physics")
                            floor=contacts.sample(data)
                            velocity=np.zeros(6)
                            mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                            upright=float(data.xmat[body].reshape(3,3)[2,2])
                            landing.observe(env.physics.time(),floor,upright,float(np.linalg.norm(velocity[3:])),data.xpos[body])
                            if landing.release_time is not None and env.physics.time()>=landing.release_time and released_position is None:
                                released_position=data.xpos[body].copy()
                            minimum_boundary=min(minimum_boundary,habitat.half_size_mm*.1-max(abs(x) for x in data.xpos[body,:2]))
                            physical.update(data.qpos.tobytes());physical.update(data.qvel.tobytes())
                            physical.update(action.tobytes());physical.update(data.xfrc_applied.tobytes())
                        yaw=math.atan2(data.xmat[body].reshape(3,3)[1,0],data.xmat[body].reshape(3,3)[0,0])
                        before_qpos,before_qvel=data.qpos.copy(),data.qvel.copy()
                        if landing.accept(response,landing.request_time is None,data.xpos[body],velocity[3:],yaw):
                            handoffs.append({
                                "time_s":landing.request_time,
                                "qpos_preserved":bool(np.array_equal(before_qpos,data.qpos)),
                                "qvel_preserved":bool(np.array_equal(before_qvel,data.qvel)),
                            })
                        log.write(json.dumps({"time_s":env.physics.time(),"position_cm":data.xpos[body].tolist(),
                                              "upright":upright,"floor_contacts":floor,
                                              "body_speed_cm_s":float(np.linalg.norm(velocity[3:])),
                                              "external_force_torque":data.xfrc_applied[body].tolist(),
                                              "landing":landing.snapshot(),"neural_response":response,"looming":features})+"\n")
                        if minimum_boundary<=.5:
                            break
                forward=0. if released_position is None else float(np.dot(data.xpos[body,:2]-released_position[:2],
                                                      [math.cos(landing.yaw),math.sin(landing.yaw)]))*10
                summary={"case":case,"landing":landing.snapshot(),"minimum_boundary_clearance_cm":float(minimum_boundary),
                         "final_upright":upright,"unassisted_forward_mm":forward,"physical_sha256":physical.hexdigest(),
                         "runtime_pose_resets":0,"post_release_assistance":data.xfrc_applied[body].tolist(),
                         "dnp10_spikes":landing.decoder.total_spikes,"network_spikes":network_spikes,
                         "handoffs":handoffs,
                         "body_mass_inertia_unchanged":bool(np.array_equal(before_model_mass,model.body_mass)
                                                            and np.array_equal(before_model_inertia,model.body_inertia)),
                         "passed":bool(landing.stable_walk_steps>=1500 and forward>=1. and minimum_boundary>.5)}
                summary["passed"] = summary["passed"] and summary["body_mass_inertia_unchanged"] and all(
                    h["qpos_preserved"] and h["qvel_preserved"] for h in handoffs)
                summary["control_passed"] = (landing.request_time is None and landing.decoder.total_spikes==0
                                            and not data.xfrc_applied.any())
                (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
                protocol=json.loads((output/"protocol.json").read_text())
                if any(hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()!=digest
                       for name,digest in protocol["source_sha256"].items()):
                    raise RuntimeError("Landing validation source changed during trial")
                accepted=summary["passed"] if case in {"intact","sham"} else summary["control_passed"]
                (output/"status.json").write_text(json.dumps({"status":"passed" if accepted else "failed"})+"\n")
                print(json.dumps(summary),flush=True)
                return summary
        finally:
            brain.close()
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed","error":str(error)})+"\n")
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=4.5)
    parser.add_argument("--seed",type=int,default=420)
    parser.add_argument("--phase",type=float,default=.5)
    parser.add_argument("--case",choices=["intact","sham","silence","visual-disconnect","no-input"],default="intact")
    args=parser.parse_args()
    result=run(args.data_dir,args.output_dir,args.seconds,args.seed,args.case,args.phase)
    if args.case in {"intact","sham"} and not result["passed"]:
        parser.exit(2,"ERROR: reduced neural landing physical thresholds failed; results preserved\n")
    if args.case not in {"intact","sham"} and not result["control_passed"]:
        parser.exit(2,"ERROR: neural landing causal control failed; results preserved\n")


if __name__=="__main__":
    main()
