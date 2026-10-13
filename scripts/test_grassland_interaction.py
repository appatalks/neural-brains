"""Actual FlyBody leg contact moves loose habitat objects; not neural feeding."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from datasets import ROOT, CATALOG
from fly_environment import Environment
from fly_flight_arena import FlyContactReader
from fly_policy import PublishedMotorPolicy, prepare_tflite_policy
from fly_unified import CONTROL_DT, WALK_EVERY, MotorAdapter, create_environment
from fly_walking import external_output
from sim_units import simulation_steps


def run(data_dir, output, seconds=.8):
    import numpy as np

    steps = simulation_steps(seconds, CONTROL_DT)
    output = external_output(output)
    output.mkdir(parents=True)
    scene = Environment.load(ROOT/"experiments/fly-walking/grassland-habitat.json")
    policy = PublishedMotorPolicy(prepare_tflite_policy(data_dir, CATALOG, "walking"))
    (output/"protocol.json").write_text(json.dumps({
        "seconds":seconds,"scope":"Learned walking leg contacts and actual free-body physics, not connectome-generated movement",
        "cases":["contact","off-path","replay"],"thresholds":{"contact_displacement_mm":.2,"off_path_seed_displacement_mm":.05,
                                                          "minimum_upright_cosine":.8},
        "mass_and_friction":"Explicit scene assumptions; not measured seed or muscle physiology",
        "source_sha256":{name:hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                         for name in ("fly_flight_arena.py","fly_unified.py","test_grassland_interaction.py")},
    },indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    try:
        results = []
        for case in ("contact","off-path","replay"):
            habitat = scene
            if case=="off-path":
                habitat = replace(scene,movable_objects=tuple(
                    replace(obj,position_mm=(-70.+i*4,-70.,obj.position_mm[2]))
                    for i,obj in enumerate(scene.movable_objects)))
            with create_environment(habitat,seconds+.1) as env:
                timestep=env.reset()
                model,data=env.physics.model.ptr,env.physics.data.ptr
                reader=FlyContactReader(model,habitat)
                adapter=MotorAdapter(env)
                initial=reader.movable_snapshot(data)
                physical=hashlib.sha256()
                body=model.body("walker/thorax").id
                min_upright=1.
                for step in range(steps):
                    if step%WALK_EVERY==0:
                        motor,_=policy.action(adapter.walking_observation(timestep.observation,2.),
                                              adapter.projections["walking"]["spec"])
                    action=adapter.walking_action(motor)
                    timestep=env.step(action)
                    reader.sample(data)
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all() or timestep.last():
                        raise RuntimeError("Grassland interaction produced invalid or terminated physics")
                    if data.xfrc_applied.any():
                        raise RuntimeError("Interaction trial unexpectedly applied external body forces")
                    min_upright=min(min_upright,float(data.xmat[body].reshape(3,3)[2,2]))
                    physical.update(data.qpos.tobytes())
                    physical.update(data.qvel.tobytes())
                    physical.update(action.tobytes())
                final=reader.movable_snapshot(data)
                displacement={a["name"]:float(np.linalg.norm(np.array(b["position_mm"][:2])-a["position_mm"][:2]))
                              for a,b in zip(initial,final)}
                result={"case":case,"objects":final,"horizontal_displacement_mm":displacement,
                        "minimum_upright_cosine":min_upright,"physical_sha256":physical.hexdigest(),
                        "external_assistance":False,"runtime_pose_resets":0}
                results.append(result)
                (output/f"{case}.json").write_text(json.dumps(result,indent=2)+"\n")
                print(json.dumps(result),flush=True)
        contact,control,replay=results
        checks={
            "actual_fly_contact_moves_seed":any(obj["fly_contact_steps"]>0 and contact["horizontal_displacement_mm"][obj["name"]]>.2
                                              for obj in contact["objects"] if obj["name"].startswith("loose_seed")),
            "off_path_seeds_do_not_move_without_contact":all(obj["fly_contact_steps"]==0
                and control["horizontal_displacement_mm"][obj["name"]]<.05
                for obj in control["objects"] if obj["name"].startswith("loose_seed")),
            "exact_physical_replay":contact["physical_sha256"]==replay["physical_sha256"],
            "walking_remains_upright":all(result["minimum_upright_cosine"]>.8 for result in results),
        }
        (output/"results.json").write_text(json.dumps({"checks":checks,"results":results},indent=2)+"\n")
        if not all(checks.values()):
            raise RuntimeError(f"Interaction checks failed: {[key for key,value in checks.items() if not value]}")
        (output/"status.json").write_text('{"status":"passed"}\n')
        return results
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed","error":str(error)})+"\n")
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=.8)
    args=parser.parse_args()
    try:
        run(args.data_dir,args.output_dir,args.seconds)
    except (OSError,ValueError,RuntimeError,ImportError) as error:
        parser.exit(1,f"ERROR: grassland interaction trial failed: {error}\n")


if __name__=="__main__":
    main()
