"""Physical learned walking with explicit engineered boundary-reference feedback."""

import argparse
import hashlib
import json
from pathlib import Path

from datasets import ROOT,CATALOG
from fly_environment import Environment
from fly_policy import PublishedMotorPolicy,prepare_policy
from fly_unified import CONTROL_DT,WALK_EVERY,MotorAdapter,create_environment
from fly_walking_navigation import WalkingNavigation
from fly_walking import external_output
from sim_units import simulation_steps


def run(data_dir,output,seconds=12.,disabled=False):
    import numpy as np
    steps=simulation_steps(seconds,CONTROL_DT)
    output=external_output(output)
    output.mkdir(parents=True)
    policy=PublishedMotorPolicy(prepare_policy(data_dir,CATALOG,"walking"))
    scene=Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        with create_environment(scene,seconds+.1) as env:
            timestep=env.reset()
            adapter=MotorAdapter(env)
            model,data=env.physics.model.ptr,env.physics.data.ptr
            body=model.body("walker/thorax").id
            navigation=WalkingNavigation(scene.half_size_mm*.1)
            navigation.begin(data.xpos[body],0)
            minimum_clearance=scene.half_size_mm*.1
            minimum_upright=1.
            with (output/"trajectory.jsonl").open("x") as log:
                for step in range(steps):
                    navigation.update(data.xpos[body],env.physics.time())
                    if step%WALK_EVERY==0:
                        motor,_=policy.action(adapter.walking_observation(timestep.observation,2.,
                                                                         navigation=None if disabled else navigation),
                                              adapter.projections["walking"]["spec"])
                    timestep=env.step(adapter.walking_action(motor))
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all() or timestep.last():
                        raise RuntimeError("Walking-boundary trial produced invalid or terminated physics")
                    minimum_clearance=min(minimum_clearance,scene.half_size_mm*.1-max(abs(v) for v in data.xpos[body,:2]))
                    minimum_upright=min(minimum_upright,float(data.xmat[body].reshape(3,3)[2,2]))
                    if step%50==0:
                        log.write(json.dumps({"time_s":env.physics.time(),"position_cm":data.xpos[body].tolist(),
                                              "upright":float(data.xmat[body].reshape(3,3)[2,2]),
                                              "reference_yaw":navigation.yaw})+"\n")
                    if minimum_clearance<=.5:
                        break
            summary={"seconds":(step+1)*CONTROL_DT,"required_seconds":seconds,
                     "minimum_boundary_clearance_cm":float(minimum_clearance),
                     "minimum_upright_cosine":minimum_upright,
                     "scope":"Engineered reference feedback through learned leg policy, not neural walking",
                     "runtime_pose_resets":0,
                     "passed":bool(step+1==steps and minimum_clearance>.5 and minimum_upright>.8)}
            (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
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
    parser.add_argument("--seconds",type=float,default=12)
    parser.add_argument("--disabled",action="store_true")
    args=parser.parse_args()
    result=run(args.data_dir,args.output_dir,args.seconds,args.disabled)
    if not result["passed"]:
        parser.exit(2,"ERROR: walking-boundary physical thresholds failed; results preserved\n")


if __name__=="__main__":
    main()
