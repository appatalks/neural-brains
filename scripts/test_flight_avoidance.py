"""Physical predictive flight avoidance trials; no neural-flight claim."""

import argparse
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_environment import Environment, HabitatObject
from fly_flight import prepare_data
from fly_flight_avoidance import FlightAvoidance, obstacle_samples, SCOPE
from fly_policy import PublishedMotorPolicy, prepare_tflite_policy
from fly_unified import CONTROL_DT, MotorAdapter, create_environment
from fly_walking import external_output


def run(data_dir, output, seconds=5., heading=0., phase=.5, disabled=False, blocker=False,
        half_size_mm=150., scene=None):
    import numpy as np
    import mujoco as mj
    from sim_units import simulation_steps

    steps = simulation_steps(seconds, CONTROL_DT)
    if not .5 <= seconds <= 30 or not math.isfinite(heading) or not 0 <= phase < 1:
        raise ValueError("Use bounded flight duration, finite heading and explicit phase in [0,1)")
    output = external_output(output)
    output.mkdir(parents=True)
    sources = {name: hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
               for name in ("fly_flight_avoidance.py", "fly_unified.py", "test_flight_avoidance.py")}
    (output/"protocol.json").write_text(json.dumps({
        "scope": SCOPE, "seconds":seconds,"initial_heading_rad":heading,"initial_wing_phase":phase,
        "disabled":disabled,"physical_blocker":blocker,"source_sha256":sources,"half_size_mm":half_size_mm,
        "thresholds":{"minimum_upright_cosine":.4,"minimum_boundary_clearance_cm":.5,
                      "minimum_height_cm":.5,"maximum_floor_contact_steps":0}},indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        paths = prepare_data(data_dir)
        policy = PublishedMotorPolicy(prepare_tflite_policy(data_dir, CATALOG, "flight"))
        habitat = replace(Environment.load(scene or ROOT/"experiments/fly-walking/planted-habitat.json"), half_size_mm=half_size_mm)
        if blocker:
            habitat=replace(habitat,objects=habitat.objects+(
                HabitatObject("avoidance_test_obstacle","sphere",(70.,0.,10.),(10.,),0.,"stone_material"),))
        with create_environment(habitat, seconds+.1, airborne=True,
                                wing_pattern=paths["wing_pattern_fmech.npy"],
                                initial_heading=heading,initial_wing_phase=phase) as env:
            timestep = env.reset()
            adapter = MotorAdapter(env)
            model,data = env.physics.model.ptr,env.physics.data.ptr
            body,ground=model.body("walker/thorax").id,model.geom("groundplane").id
            avoidance=FlightAvoidance(half_size_mm*.1)
            from fly_flight_arena import FlyContactReader
            contact_reader=FlyContactReader(model,habitat)
            avoidance.begin(data.xpos[body],0.,heading)
            initial_mass,initial_inertia=model.body_mass.copy(),model.body_inertia.copy()
            minimum_clearance=half_size_mm*.1
            minimum_height=1.
            minimum_upright=1.
            contacts=0
            obstacle_contacts=0
            minimum_obstacle_clearance=None
            obstacle_id=model.geom("avoidance_test_obstacle").id if blocker else None
            physical=hashlib.sha256()
            observed_rays=0
            final_step=0
            yaw_change=0.
            last_yaw=heading
            failure=None
            with (output/"trajectory.jsonl").open("x") as log:
                for step in range(steps):
                    t=step*CONTROL_DT
                    if step%50==0:
                        samples=obstacle_samples(model,data,body,avoidance.known_obstacle_ids)
                        observed_rays+=sum(sample["geom_id"]==obstacle_id for sample in samples)
                        avoidance.update(data.xpos[body],t,samples)
                    observation=adapter.flight_observation(timestep.observation,
                                                          navigation=None if disabled else avoidance)
                    motor,_=policy.action(observation,adapter.projections["flight"]["spec"])
                    action=adapter.flight_action(motor)
                    timestep=env.step(action)
                    physical.update(data.qpos.tobytes())
                    physical.update(data.qvel.tobytes())
                    physical.update(action.tobytes())
                    final_step=step+1
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all() or timestep.last():
                        raise RuntimeError("Avoidance produced invalid or terminated physics")
                    if data.xfrc_applied.any():
                        raise RuntimeError("Avoidance trial applied unexpected external assistance")
                    minimum_clearance=min(minimum_clearance,half_size_mm*.1-max(abs(x) for x in data.xpos[body,:2]))
                    minimum_height=min(minimum_height,float(data.xpos[body,2]))
                    minimum_upright=min(minimum_upright,float(data.xmat[body].reshape(3,3)[2,2]))
                    contacts+=int(contact_reader.sample(data)>0)
                    if blocker:
                        clearance=math.dist(data.xpos[body],data.geom_xpos[obstacle_id])-1.
                        minimum_obstacle_clearance=clearance if minimum_obstacle_clearance is None else min(clearance,minimum_obstacle_clearance)
                        obstacle_contacts+=int(any(c.geom1==obstacle_id or c.geom2==obstacle_id for c in data.contact[:data.ncon]))
                    if step%50==0:
                        rotation=data.xmat[body].reshape(3,3)
                        yaw=math.atan2(rotation[1,0],rotation[0,0])
                        yaw_change+=abs(math.atan2(math.sin(yaw-last_yaw),math.cos(yaw-last_yaw)))
                        last_yaw=yaw
                        log.write(json.dumps({"time_s":env.physics.time(),"position_cm":data.xpos[body].tolist(),
                                              "upright_cosine":float(rotation[2,2]),"navigation":avoidance.snapshot()})+"\n")
                    if minimum_clearance<=.5 or contacts or obstacle_contacts or minimum_height<.5 or minimum_upright<.4:
                        failure="boundary/contact/height/attitude threshold"
                        break
            unchanged=np.array_equal(initial_mass,model.body_mass) and np.array_equal(initial_inertia,model.body_inertia)
            summary={"passed":failure is None and final_step==steps and unchanged,
                     "failure":failure,"completed_seconds":final_step*CONTROL_DT,"required_seconds":seconds,
                     "minimum_boundary_clearance_cm":minimum_clearance,"minimum_height_cm":minimum_height,
                     "minimum_upright_cosine":minimum_upright,"floor_contact_steps":contacts,
                     "physical_yaw_travel_rad":yaw_change,"body_mass_inertia_unchanged":bool(unchanged),
                     "physical_sha256":physical.hexdigest(),"obstacle_contact_steps":obstacle_contacts,
                     "observed_blocker_rays":observed_rays,"minimum_obstacle_clearance_cm":minimum_obstacle_clearance,
                     "runtime_pose_resets":0,"external_assistance":False,"navigation":avoidance.snapshot()}
            (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
            if any(hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()!=digest for name,digest in sources.items()):
                raise RuntimeError("Avoidance source files changed during physical validation")
            (output/"status.json").write_text(json.dumps({"status":"passed" if summary["passed"] else "failed"})+"\n")
            print(json.dumps(summary),flush=True)
            return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed","error":str(error)})+"\n")
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=5)
    parser.add_argument("--heading",type=float,default=0)
    parser.add_argument("--phase",type=float,default=.5)
    parser.add_argument("--disabled",action="store_true")
    parser.add_argument("--blocker",action="store_true")
    parser.add_argument("--half-size-mm",type=float,default=150)
    parser.add_argument("--scene",type=Path)
    args=parser.parse_args()
    try:
        result=run(args.data_dir,args.output_dir,args.seconds,args.heading,args.phase,args.disabled,args.blocker,
                   args.half_size_mm,args.scene)
    except (OSError,ValueError,RuntimeError,ImportError) as error:
        parser.exit(1,f"ERROR: avoidance trial failed: {error}\n")
    if not result["passed"]:
        parser.exit(2,"ERROR: physical avoidance thresholds failed; results preserved\n")


if __name__=="__main__":
    main()
