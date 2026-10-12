"""Independent brain/body flies, one authoritative world and one browser server."""

import json
import math
import time
from contextlib import ExitStack
from dataclasses import replace

from datasets import ROOT,CATALOG
from fly_agent import FlyAgent
from fly_dashboard import Dashboard,DEFAULT_PORT,validate_app_port
from fly_connections import ConnectionIndex
from fly_environment import Environment,environment_dict
from fly_feeding import FeedingConfig
from fly_objects import Objects,set_flight_object_position
from fly_policy import PublishedMotorPolicy,prepare_policy
from fly_unified import CONTROL_DT,create_environment,prepare_data
from fly_water import FluidPhysics
from fly_world_renderer import BrowserInputs,WorldRenderer
from sim_units import simulation_steps


def run(data_dir,output,scene,feeding_config,objects_path=None,seconds=None,
        port=DEFAULT_PORT,arena_half_size_mm=112.5,fly_count=2,
        brain_guided_walking=True,flight_avoidance=True,neural_leg_extension=True,
        brain_linked_landing=True,landing_surface_vision=True,fluid_physics=False,
        controlled_test=False,test_stimulus=False,actuator_recovery=False):
    import mujoco as mj
    import numpy as np

    validate_app_port(port)
    if type(fly_count) is not int or not 1<=fly_count<=3:
        raise ValueError("Shared-agent app requires1..3 independent brain/body pairs")
    output,data_dir=output.expanduser().resolve(),data_dir.expanduser().resolve()
    if output.exists() or any(path==ROOT or ROOT in path.parents for path in (output,data_dir)):
        raise ValueError("Choose existing external inputs and a new external output directory")
    if seconds is not None and (not math.isfinite(seconds) or not 0<seconds<=60):
        raise ValueError("Bounded multi-fly validation requires0..60seconds")
    target=simulation_steps(seconds,CONTROL_DT) if seconds is not None else None
    if seconds is not None:simulation_steps(seconds,.01)
    if controlled_test and seconds is None or test_stimulus and seconds is None:
        raise ValueError("Explicit multi-fly controls require bounded duration")
    if test_stimulus:
        raise ValueError("Multi-fly artificial visual probes are not supported; use physical sensory inputs")
    if landing_surface_vision and not brain_linked_landing:
        raise ValueError("Multi-fly surface input requires brain-linked landing")
    habitat=replace(Environment.load(scene),half_size_mm=arena_half_size_mm)
    food=FeedingConfig.load(feeding_config)
    placed=Objects(habitat.half_size_mm)
    if objects_path is not None:placed.load(objects_path)
    output.mkdir(parents=True)
    (output/"environment.json").write_text(json.dumps(environment_dict(habitat),indent=2)+"\n")
    (output/"feeding-config.json").write_text(feeding_config.read_text())
    placed.save(output/"objects.json")
    requested=None
    selected=0
    controls={"paused":False,"sugar_enabled":True,"finger_enabled":False,"follow_camera":False,
              "obstacles":True,"slippery":False,"object_kind":None,"removal_mode":False}
    closed=False
    stopped=False
    safety=None
    error_message=None
    steps=0
    epoch=0
    bump_until=0.
    eye_time=None
    next_eyes=0.
    cursor_valid=False
    finger=np.array([0.,0.,.15])
    pointer=finger.copy()
    wall=time.perf_counter()
    paths=prepare_data(data_dir)
    spawn=[value*.1 for value in habitat.spawn_position_mm] if habitat.spawn_position_mm is not None else None
    try:
        with ExitStack() as resources:
            env=create_environment(habitat,3600,wing_pattern=paths["wing_pattern_fmech.npy"],
                                   interactive=True,initial_position=spawn,fluid_physics=fluid_physics,fly_count=fly_count)
            resources.callback(env.close)
            timestep=env.reset()
            model,data=env.physics.model.ptr,env.physics.data.ptr
            walking=PublishedMotorPolicy(prepare_policy(data_dir,CATALOG,"walking"))
            flying=PublishedMotorPolicy(prepare_policy(data_dir,CATALOG,"flight"))
            agents=[]

            def configure():
                for geom in range(model.ngeom):
                    name=model.geom(geom).name or ""
                    if name.startswith("walker"):
                        model.geom_group[geom]=1
                        if name.startswith("walker_1/"):model.geom_rgba[geom,:3]=[.25,.7,.4]
                        elif name.startswith("walker_2/"):model.geom_rgba[geom,:3]=[.95,.6,.18]
                for item in placed.placements:set_flight_object_position(model,data,item["name"],item["position_mm"])
                mj.mj_forward(model,data)
            configure()

            def build_agents(folder):
                folder.mkdir(exist_ok=True)
                result=[]
                for index in range(fly_count):
                    actor=FlyAgent(env,index,data_dir,folder/f"fly-{index+1}",food,paths,walking,flying,
                        brain_guided_walking,flight_avoidance,neural_leg_extension,brain_linked_landing,landing_surface_vision,
                        actuator_recovery)
                    resources.callback(actor.brain.close)
                    result.append(actor)
                    (actor.output/"brain-metadata.json").write_text(json.dumps(actor.brain.metadata)+"\n")
                return result

            agents=build_agents(output/"brains")
            initial_mass,initial_inertia=model.body_mass.copy(),model.body_inertia.copy()
            if len({actor.brain.process.pid for actor in agents})!=fly_count:
                raise RuntimeError("Every fly must own a distinct whole-brain worker")
            water=FluidPhysics(model,habitat,force_dt=CONTROL_DT) if fluid_physics else None
            metadata={**agents[0].brain.metadata,"fly_count":fly_count,
                      "independent_brains":[{"id":actor.id,"seed":food.seed+actor.index,
                                             "neurons":actor.brain.metadata["neurons"]} for actor in agents],
                      "multi_fly_scope":"Independent whole-brain workers, physical bodies and motor state in one shared MuJoCo world. No inter-brain synapses or calibrated social perception."}
            connections=ConnectionIndex(metadata["connection_index_dir"],metadata["neuron_ids"],metadata["upstream_commit"])
            inputs=BrowserInputs()
            app=Dashboard(output,metadata,port,connections,inputs)
            resources.callback(app.close)
            world=WorldRenderer(model,data,habitat.half_size_mm*.1,agents[0].body,inputs,app.publish_world,
                                unit_scale=.1,initial_distance=2.)
            resources.callback(world.close)
            renderer=resources.enter_context(mj.Renderer(model,height=256,width=256))
            eye_option=mj.MjvOption();eye_option.geomgroup[1]=0;eye_option.geomgroup[2]=0
            events=resources.enter_context((output/"app-events.jsonl").open("x"))
            log=resources.enter_context((output/"multi-neural-flight.jsonl").open("x"))
            mocap=model.body_mocapid[model.body("virtual_finger").id]
            finger_geom=model.geom("virtual_finger_tip").id
            marker=model.geom("pointer_target").id
            ground=model.geom("groundplane").id
            original_friction=model.geom_friction[ground].copy()
            print(f"{fly_count} independent brain/body flies: {app.url}",flush=True)
            (output/"status.json").write_text('{"status":"running"}\n')

            def publish(refresh_eyes=False):
                nonlocal eye_time,next_eyes
                actor=agents[selected]
                if actor.reply is None:return
                eyes=None
                if refresh_eyes or env.physics.time()>=next_eyes:
                    images=[]
                    for camera in actor.eyes:
                        renderer.update_scene(data,camera=camera,scene_option=eye_option)
                        images.append(renderer.render().copy())
                    eyes=np.concatenate(images,axis=1)
                    eye_time=env.physics.time();next_eyes=eye_time+.1
                packet={**actor.reply,"observed_fly_id":actor.id,"fly_count":fly_count,
                        "flies":[agent.snapshot() for agent in agents],"habitat_time_s":env.physics.time(),
                        "eye_time_s":eye_time,"status":"safety stopped" if stopped else actor.phase,
                        "motor_phase":actor.phase,"paused":stopped or controls["paused"],
                        "safety_notice":safety,"environment_controls":controls.copy(),
                        "interaction_error":error_message,"editable_objects":len(placed.placements),
                        "virtual_finger_available":True,"controller_scope":metadata["multi_fly_scope"],
                        "eye_scope":"Selected fly rectilinear eyes; all fly geoms hidden from eye rendering. No calibrated social visual pathway.",
                        "walking_control":actor.control.snapshot() if actor.control is not None else None,
                        "brain_linked_landing":actor.landing.snapshot() if actor.landing is not None else None,
                        "movable_objects":actor.contacts.movable_snapshot(data),
                        "water":water.snapshot() if water is not None else
                            {"surface_mode":"rigid-prototype","scope":"Water-colored fixed collision surface; no fluid forces."}}
                if actor.control is None:packet.pop("walking_control")
                if actor.landing is None:packet.pop("brain_linked_landing")
                app.publish(packet,eyes)
                world.submit(model,data,env.physics.time(),controls["follow_camera"])

            while not closed and (target is None or steps<target):
                world.check()
                while not inputs.empty():
                    event=inputs.get_nowait()
                    events.write(json.dumps({"time_s":env.physics.time(),"input":event})+"\n");events.flush()
                    kind=event["kind"]
                    if kind=="inspect_fly":
                        if event["fly"]>fly_count:
                            error_message="Requested fly is not part of this episode."
                        else:
                            selected=event["fly"]-1;world.select_body(agents[selected].body);publish(True)
                    elif kind=="fly_count":
                        if controlled_test or seconds is not None:
                            error_message="Bounded multi-fly validation locks population changes."
                        elif event["count"]!=fly_count:
                            requested=event["count"];closed=True
                    elif kind=="pointer":
                        point=world.target(event["x"]*1280,(1-event["y"])*960,plane_z=.15)
                        cursor_valid=point is not None
                        if cursor_valid:
                            pointer[:]=point;pointer[:2]=np.clip(pointer[:2],-habitat.half_size_mm*.1+.15,habitat.half_size_mm*.1-.15)
                    elif kind!="key":
                        controls["follow_camera"]=False
                    else:
                        key=event["key"]
                        if controlled_test and key not in {"Q","P","C"}:
                            error_message="Controlled validation disables physical edits/reset.";continue
                        if key=="Q":closed=True
                        elif key=="P":
                            if stopped:error_message="Safety stop requires explicit Reset."
                            else:controls["paused"]=not controls["paused"]
                            wall=time.perf_counter()
                        elif key=="R":
                            for agent in agents:agent.restore_motor_gains()
                            timestep=env.reset();model,data=env.physics.model.ptr,env.physics.data.ptr
                            configure();epoch+=1;steps=0
                            for agent in agents:agent.reset()
                            water=FluidPhysics(model,habitat,force_dt=CONTROL_DT) if fluid_physics else None
                            stopped=False;safety=None;next_eyes=0.;eye_time=None
                        elif key=="C":controls["follow_camera"]=not controls["follow_camera"]
                        elif key=="H":controls["finger_enabled"]=not controls["finger_enabled"]
                        elif key=="T":controls["sugar_enabled"]=not controls["sugar_enabled"]
                        elif key in {"1","2","3"}:
                            controls["object_kind"]={"1":"box","2":"sphere","3":None}[key]
                            controls["removal_mode"]=key=="3"
                            if cursor_valid:
                                try:
                                    if key=="3":
                                        item=placed.remove()
                                        set_flight_object_position(model,data,item["name"])
                                    else:
                                        item=placed.place(controls["object_kind"],(pointer*10).tolist())
                                        set_flight_object_position(model,data,item["name"],item["position_mm"])
                                    placed.save(output/"objects.json");mj.mj_forward(model,data)
                                except ValueError as error:
                                    error_message=str(error)
                                    print(f"WARNING: object edit rejected: {error}",file=__import__("sys").stderr)
                        elif key=="F":
                            controls["slippery"]=not controls["slippery"]
                            model.geom_friction[ground]=(.01,.001,.00001) if controls["slippery"] else original_friction
                        elif key=="B":bump_until=env.physics.time()+.03
                        elif key=="O":
                            controls["obstacles"]=not controls["obstacles"]
                            for terrain in habitat.terrain:
                                geom=model.geom(terrain.name).id
                                model.geom_pos[geom,2]=terrain.position_mm[2]*.1 if controls["obstacles"] else -10.
                if closed:break
                if controls["paused"] or stopped:
                    publish();time.sleep(.01);continue
                now=time.perf_counter();wall_dt=min(.1,max(0.,now-wall));wall=now
                if controls["finger_enabled"]:
                    delta=pointer-finger;distance=float(np.linalg.norm(delta))
                    if distance:finger+=delta*min(1.,2*wall_dt/distance)
                data.mocap_pos[mocap]=finger if controls["finger_enabled"] else [0,0,-10]
                model.geom_pos[marker]=pointer;model.geom_rgba[marker,3]=int(cursor_valid)
                mj.mj_forward(model,data)
                for agent in agents:agent.begin_brain(finger,finger_geom,controls["sugar_enabled"],controls["finger_enabled"])
                for agent in agents:agent.prepare_interval()
                for _ in range(50):
                    data.xfrc_applied.fill(0)
                    actions=[agent.action(timestep.observation,steps) for agent in agents]
                    if env.physics.time()<bump_until:data.xfrc_applied[agents[selected].body,1]+=.5
                    if water is not None:water.apply(data)
                    timestep=env.step(np.concatenate(actions));steps+=1
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                        raise RuntimeError("Shared multi-fly physical state became nonfinite")
                    for agent in agents:
                        reason=agent.observe()
                        if reason:stopped=True;safety=reason
                    if timestep.last():raise RuntimeError("Shared task terminated; no automatic body reset")
                for agent in agents:agent.accept_brain(stopped)
                publish()
                log.write(json.dumps({"time_s":env.physics.time(),
                    "flies":[{"id":agent.id,"packet":agent.reply,"state":agent.snapshot(),
                              "exposure":agent.exposure,"walking_drive_Hz":agent.drive,
                              "landing_assistance_force_torque":agent.landing_force.tolist()}
                             for agent in agents]})+"\n");log.flush()
                if stopped and target is not None:break
            placed.save(output/"objects.json")
            unchanged=np.array_equal(initial_mass,model.body_mass) and np.array_equal(initial_inertia,model.body_inertia)
            if not unchanged:raise RuntimeError("Shared fly body mass/inertia changed")
            summary={"status":"reconfigure_requested" if requested is not None else "closed_by_user" if closed else
                     "safety_stopped" if stopped else "completed","seconds":env.physics.time(),"fly_count":fly_count,
                     "requested_fly_count":requested,"same_body_mass_inertia_unchanged":bool(unchanged),
                     "brain_seeds":[food.seed+index for index in range(fly_count)],
                     "independent_whole_brain_workers":len({agent.brain.process.pid for agent in agents}),
                     "neurons_per_brain":[agent.brain.metadata["neurons"] for agent in agents],
                     "safety_reason":safety,"flies":[agent.snapshot() for agent in agents],
                     "takeoff_handoffs":[agent.handoffs for agent in agents],
                     "landing_handoffs":[agent.landing_handoffs for agent in agents],
                     "scope":metadata["multi_fly_scope"]}
            summary["actuator_recovery_enabled"]=actuator_recovery
            (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status":summary["status"]})+"\n")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed","error":str(error)})+"\n")
        raise
