"""Namespaced control and observations for independent flies in one MuJoCo world."""

from types import SimpleNamespace


def spawn_layout(habitat,fly_count):
    import math
    if type(fly_count) is not int or not 1<=fly_count<=3:
        raise ValueError("Spawn layout requires1..3 actual flies")
    half=habitat.half_size_mm*.1
    first=[value*.1 for value in habitat.spawn_position_mm] if habitat.spawn_position_mm is not None else [-.4*half,-.6*half,.1278]
    candidates=[(first,0.),([-.4*half,.6*half,.1278],0.),([.4*half,-.6*half,.1278],math.pi)]
    for position,_ in candidates[:fly_count]:
        if max(abs(value) for value in position[:2])>=half-.5:
            raise ValueError("Separated dry-soil spawn requires valid arena clearance")
    return candidates[:fly_count]


def surrounding_drive(drive,cues,model,data,body,peer_bodies):
    import math
    import numpy as np
    result=dict(drive)
    details={**cues,"peer_cues":[],"scope":cues["scope"]+
             " Peer proximity and early obstacle stopping are privileged geometry-to-P9/FG assumptions, not calibrated social/tactile receptors."}
    if not cues.get("active"):return result,details
    if cues.get("ranges_cm",[2.5,2.5,2.5])[1]<1.2:
        result["FG"]=150.
    rotation=data.xmat[body].reshape(3,3)
    yaw=math.atan2(rotation[1,0],rotation[0,0])
    forward=np.array([math.cos(yaw),math.sin(yaw)])
    for peer in peer_bodies:
        if peer==body:continue
        relative=data.xpos[peer,:2]-data.xpos[body,:2]
        distance=float(np.linalg.norm(relative))
        along=float(relative@forward)
        if distance<1.8 and along>0 and along>distance*.4:
            cross=forward[0]*relative[1]-forward[1]*relative[0]
            key="P9_right" if cross>0 else "P9_left"
            result[key]=150.
            if distance<.9:result["FG"]=150.
            details["peer_cues"].append({"body_id":int(peer),"distance_cm":distance,"input":key,
                                        "stop_input":distance<.9})
    return result,details


def actor_specifications(walkers,physics):
    import numpy as np
    from dm_env import specs
    result=[]
    for walker in walkers:
        actuators=walker.mjcf_model.find_all("actuator")
        local=[index for group,indices in walker._action_indices.items()
               if group!="user" and indices and walker._ctrl_indices[group]
               for index in walker._ctrl_indices[group]]
        names=[actuators[index].name for index in local]
        global_ids=np.array([physics.model.name2id(f"{walker.name}/{name}","actuator") for name in names])
        if len(set(global_ids.tolist()))!=len(names):
            raise ValueError("Each fly requires disjoint uniquely named actuator channels")
        limits=physics.model.actuator_ctrlrange[global_ids]
        result.append((specs.BoundedArray((len(names),),float,limits[:,0],limits[:,1],
                                         name="\t".join(names)),global_ids))
    ids=[value for _,indices in result for value in indices]
    if len(set(ids))!=len(ids):
        raise ValueError("Independent fly controls cannot share physical actuators")
    return result


def apply_actor_actions(walkers,physics,action,specifications=None):
    import numpy as np
    specifications=actor_specifications(walkers,physics) if specifications is None else specifications
    if action.shape!=(sum(spec.shape[0] for spec,_ in specifications),) or not np.isfinite(action).all():
        raise ValueError("Shared-world action requires finite controls for every fly")
    ctrl=np.zeros(physics.model.nu)
    offset=0
    for walker,(spec,indices) in zip(walkers,specifications):
        local=action[offset:offset+spec.shape[0]]
        if np.any(local<spec.minimum) or np.any(local>spec.maximum):
            raise ValueError("Fly action exceeds its named published controller bounds")
        walker._prev_action[:]=local
        ctrl[indices]=local
        offset+=spec.shape[0]
    physics.set_control(ctrl)


def actor_environment(env,index,wing_pattern):
    import numpy as np
    from flybody.tasks.pattern_generators import WingBeatPatternGenerator
    walker=env.task.walkers[index]
    specification,_=actor_specifications([walker],env.physics)[0]
    joints=[joint for joint in walker.mjcf_model.find_all("joint")
            if any(axis in joint.name for axis in ("yaw","roll","pitch"))]
    task=SimpleNamespace(walker=walker,_wing_joints=joints,
                         _wing_springrefs=np.array([float(j.springref or j.dclass.joint.springref or 0) for j in joints]),
                         walk_origin=walker.get_pose(env.physics)[0].copy(),walk_start=env.physics.time(),
                         launch_time=None,launch_origin=None,landing_time=None,landing_origin=None)
    task.wbpg=WingBeatPatternGenerator(base_pattern_path=str(wing_pattern))
    task.wbpg.reset(initial_phase=.5)
    return SimpleNamespace(physics=env.physics,task=task,action_spec=lambda:specification)


def actor_observation(observation,walker):
    prefix=walker.name+"/"
    result={"walker/"+key[len(prefix):]:value for key,value in observation.items() if key.startswith(prefix)}
    if not result:
        raise ValueError(f"No actual physical observations for {walker.name}")
    return result
