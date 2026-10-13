"""Bounded motor-only regression for off-center takeoff; not a neural causality test."""

import argparse
import json
import math
from pathlib import Path

from datasets import ROOT,CATALOG
from fly_environment import Environment
from fly_flight import prepare_data
from fly_flight_avoidance import FlightAvoidance,obstacle_samples
from fly_flight_arena import FlyContactReader
from fly_policy import PublishedMotorPolicy,prepare_tflite_policy
from fly_takeoff import assisted_force
from fly_unified import create_environment,MotorAdapter,CONTROL_DT
from fly_walking import external_output


def run(data_dir,output):
    import numpy as np
    import mujoco as mj
    from flybody.quaternions import mult_quat
    output=external_output(output)
    output.mkdir(parents=True)
    paths=prepare_data(data_dir)
    policy=PublishedMotorPolicy(prepare_tflite_policy(data_dir,CATALOG,"flight"))
    scene=Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json")
    cases=[("center",[0,0,.1278],0.),("reported-corner",[6.75,9.65,.1278],0.),
           ("north-outward",[6.75,9.65,.1278],math.pi/2),
           ("west-outward",[-9.65,-6.75,.1278],math.pi)]
    results=[]
    for name,position,yaw in cases:
        with create_environment(scene,3.1,wing_pattern=paths["wing_pattern_fmech.npy"],
                                initial_position=position,initial_heading=yaw) as env:
            timestep=env.reset()
            adapter=MotorAdapter(env)
            model,data=env.physics.model.ptr,env.physics.data.ptr
            body=model.body("walker/thorax").id
            mass=sum(model.body_mass[i] for i in range(model.nbody)
                     if (mj.mj_id2name(model,mj.mjtObj.mjOBJ_BODY,i) or "").startswith("walker"))
            before_pos,before_vel=data.qpos.copy(),data.qvel.copy()
            env.task.begin_launch(env.physics)
            controller=FlightAvoidance(scene.half_size_mm*.1)
            controller.begin(data.xpos[body],0.,yaw,launch=True)
            preserved=np.array_equal(before_pos,data.qpos) and np.array_equal(before_vel,data.qvel)
            reader=FlyContactReader(model,scene)
            clearance=11.25
            height=10.
            upright=1.
            floor_ticks=0
            with (output/(name+".jsonl")).open("x") as log:
                for step in range(15000):
                    t=step*CONTROL_DT
                    if step%50==0:
                        controller.update(data.xpos[body],t,obstacle_samples(model,data,body,controller.known_obstacle_ids))
                    motor,_=policy.action(adapter.flight_observation(timestep.observation,navigation=controller),
                                          adapter.projections["flight"]["spec"])
                    data.xfrc_applied[body]=0.
                    if t<.3:
                        target,velocity,yaw_target=controller.reference(t)
                        quat=mult_quat(np.array([math.cos(yaw_target/2),0,0,math.sin(yaw_target/2)]),
                                       np.array([math.cos(math.radians(47.5)/2),0,-math.sin(math.radians(47.5)/2),0]))
                        rotation=np.zeros(9)
                        mj.mju_quat2Mat(rotation,quat)
                        body_velocity=np.zeros(6)
                        mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,body_velocity,False)
                        data.xfrc_applied[body]=assisted_force(mass,data.xpos[body],body_velocity,
                            data.xmat[body].reshape(3,3),rotation.reshape(3,3),np.array(target),velocity)
                    timestep=env.step(adapter.flight_action(motor))
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                        raise RuntimeError("Launch-clearance regression produced invalid physics")
                    clearance=min(clearance,11.25-max(abs(v) for v in data.xpos[body,:2]))
                    contacts=reader.sample(data)
                    if t>=.3:
                        height=min(height,float(data.xpos[body,2]))
                        upright=min(upright,float(data.xmat[body].reshape(3,3)[2,2]))
                        floor_ticks+=int(contacts>0)
                    if step%50==0:
                        log.write(json.dumps({"time_s":t,"position_cm":data.xpos[body].tolist(),
                                              "controller":controller.snapshot()})+"\n")
                    if clearance<=.5:
                        break
            result={"case":name,"seconds":(step+1)*CONTROL_DT,"minimum_clearance_cm":float(clearance),
                    "minimum_flight_height_cm":height,"minimum_flight_upright":upright,
                    "flight_floor_contact_ticks":floor_ticks,"handoff_preserved":bool(preserved),
                    "passed":bool(step==14999 and clearance>.5 and height>.5 and upright>.4 and floor_ticks==0)}
            results.append(result)
            (output/"results.json").write_text(json.dumps(results,indent=2)+"\n")
            print(json.dumps(result),flush=True)
    (output/"status.json").write_text(json.dumps({"status":"passed" if all(r["passed"] for r in results) else "failed"})+"\n")
    if not all(r["passed"] for r in results):
        raise RuntimeError("Off-center launch regression failed; results preserved")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    run(args.data_dir,args.output_dir)
