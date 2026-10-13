"""Single-browser, single-body experimental walking and GF-assisted flight."""

import argparse
import hashlib
import json
import math
import sys
import time
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_connections import ConnectionIndex
from fly_dashboard import DEFAULT_PORT, Dashboard, validate_app_port
from fly_environment import Environment, environment_dict
from fly_flight_arena import FlyContactReader
from fly_feeding import BrainClient, FeedingConfig, default_feeding_config
from fly_flight import prepare_data
from fly_looming import GRADED_ENCODER, SphereLooming, SphereVision, LandingSurfaceVision, finger_visibility, graded_visual_rates
from fly_objects import Objects, set_flight_object_position
from fly_policy import PublishedMotorPolicy, prepare_tflite_policy
from fly_pointer_motion import capped_motion
from fly_navigation import FlightNavigation, landing_assistance
from fly_flight_avoidance import FlightAvoidance, obstacle_samples, SCOPE as AVOIDANCE_SCOPE, MIN_HALF_SIZE_CM
from fly_takeoff import assisted_force
from fly_leg_extension import DNP10_IDS, LegExtension, SCOPE as LEG_EXTENSION_SCOPE
from fly_neural_landing import NeuralLanding, SCOPE as LANDING_SCOPE
from fly_walking_navigation import WalkingNavigation
from fly_brain_walk import WalkingControl, WalkingReference, scene_drive, prescribed_drive, profile_metrics, support_height, SCOPE as WALK_SCOPE, DRIVE_SCOPE
from fly_water import FluidPhysics, SCOPE as WATER_SCOPE
from fly_unified import CONTROL_DT, WALK_EVERY, MotorAdapter, create_environment
from fly_world_renderer import BrowserInputs, WorldRenderer
from sim_units import simulation_steps


def flight_test_passed(summary):
    return (
        summary["status"]=="completed" and summary["same_body_mass_inertia_unchanged"]
        and summary["initial_ground_contact_observed"] and bool(summary["handoffs"])
        and all(h["qpos_preserved"] and h["qvel_preserved"] for h in summary["handoffs"])
        and summary["flight_steps"]>=2500 and summary["flight_floor_contact_steps"]==0
        and not summary["safety_stopped"]
    )


def cycle_test_passed(summary):
    return flight_test_passed(summary) and (
        summary["landed_at_s"] is not None
        and summary["stable_unassisted_post_landing_steps"] >= 1500
    )


def run(data_dir, output, scene, feeding_config, objects_path=None, seconds=None,
        port=DEFAULT_PORT, arena_half_size_mm=112.5, test_stimulus=False, test_approach=False,
        engineered_navigation=False, neural_leg_extension=False, test_leg_extension=False,
        graded_vision=False, flight_avoidance=False, brain_linked_landing=False,
        test_brain_landing=False, landing_surface_vision=False,research_dnp10=None,controlled_test=False,
        walking_readouts=False, brain_guided_walking=False, test_walking_control=False,
        research_walking_control=None, fluid_physics=False):
    import mujoco as mj
    import numpy as np

    validate_app_port(port)
    if controlled_test and (seconds is None or not (test_stimulus or test_walking_control or brain_guided_walking)):
        raise ValueError("Controlled-input lock requires a bounded stimulus or brain-guided walking experiment")
    output, data_dir = output.expanduser().resolve(), data_dir.expanduser().resolve()
    if any(p == ROOT or ROOT in p.parents for p in [output, data_dir]) or output.exists():
        raise ValueError("Choose external inputs and a new external output directory")
    if not math.isfinite(arena_half_size_mm) or arena_half_size_mm < 30:
        raise ValueError("Explicit flight arena half-size must be at least 30 mm")
    target_steps = simulation_steps(seconds, CONTROL_DT) if seconds is not None else None
    if seconds is not None:
        simulation_steps(seconds, .01)
        if not 0 < seconds <= 60:
            raise ValueError("Bounded flight app test must be in (0, 60] seconds")
    if (test_stimulus or test_approach) and seconds is None:
        raise ValueError("Explicit test stimuli require a bounded duration")
    if test_stimulus and test_approach:
        raise ValueError("Physical approach and direct neural stimulus are distinct tests")
    if neural_leg_extension and engineered_navigation:
        raise ValueError("Reduced neural leg extension and experimental assisted landing must be tested separately")
    if flight_avoidance and engineered_navigation:
        raise ValueError("Flight avoidance and failed engineered landing experiments must remain separate")
    if brain_linked_landing and engineered_navigation:
        raise ValueError("Actual-DN landing and prior timer-based landing experiments must remain separate")
    if landing_surface_vision and (not brain_linked_landing or graded_vision):
        raise ValueError("Approximate landing surfaces require brain-linked landing and the preserved binary worker")
    if research_dnp10 is not None and (seconds is None or not brain_linked_landing or research_dnp10 not in {"silence","sham"}):
        raise ValueError("DNp10 research intervention requires bounded brain-linked landing experiment")
    if test_brain_landing and (not brain_linked_landing or not test_stimulus or seconds is None or seconds<6):
        raise ValueError("Brain-linked cycle test requires upstream launch test, enabled landing and >=6s")
    if flight_avoidance and arena_half_size_mm*.1 < MIN_HALF_SIZE_CM-1e-9:
        raise ValueError("Flight avoidance requires arena half-size >=79.55 mm")
    if test_leg_extension and (
        not test_stimulus or seconds is None or seconds < 1.2 or engineered_navigation
    ):
        raise ValueError("Flight leg test requires an explicit upstream launch test and at least 1.2 s; no assisted landing")
    if test_walking_control and (
        not brain_guided_walking or seconds is None or seconds < 5 or test_stimulus or test_approach
    ):
        raise ValueError("Walking control test requires explicit hybrid,>=5s and no visual launch test")
    if research_walking_control is not None and (
        not brain_guided_walking or seconds is None
        or research_walking_control not in {"sham", "source-cut", "output-silence", "motor-disconnect"}
    ):
        raise ValueError("Walking research control requires bounded explicit hybrid experiment")
    habitat = replace(Environment.load(scene), half_size_mm=arena_half_size_mm)
    if fluid_physics and not habitat.water_regions:
        raise ValueError("--fluid-physics requires declared water in the selected scene")
    food = FeedingConfig.load(feeding_config)
    objects = Objects(habitat.half_size_mm)
    if objects_path:
        objects.load(objects_path)
    output.mkdir(parents=True)
    (output/"status.json").write_text('{"status":"loading"}\n')
    (output/"environment.json").write_text(json.dumps(environment_dict(habitat), indent=2)+"\n")
    (output/"objects.json").write_text(json.dumps(objects.placements, indent=2)+"\n")
    (output/"feeding-config.json").write_text(json.dumps(json.loads(feeding_config.read_text()),indent=2)+"\n")
    env = None
    started = time.perf_counter()
    total_steps = 0
    episode_steps = 0
    episode = 0
    trigger_time = None
    controls = {
        "paused": False, "finger_enabled": False, "sugar_enabled": True,
        "slippery": False, "follow_camera": True,
    }
    closed = False
    requested_fly_count=None
    safety_stopped = False
    error_message = None
    phase = "walking"
    handoffs = []
    flight_steps = 0
    floor_contact_steps = 0
    eye_count = 0
    initial_contact = False
    landed_at = None
    landing_contacts = 0
    post_landing_steps = 0
    navigation = FlightNavigation(arena_half_size_mm*.1) if engineered_navigation else None
    avoidance = FlightAvoidance(arena_half_size_mm*.1) if flight_avoidance else None
    minimum_flight_clearance_cm = None
    minimum_flight_height_cm = None
    minimum_flight_upright = None
    landing_motor = None
    walk_motor = None
    stable_post_landing_steps = 0
    neural_landing_handoffs=[]
    release_position=None
    post_release_displacement_mm=0.
    maximum_post_release_landing_assistance=0.
    walking_navigation=WalkingNavigation(arena_half_size_mm*.1) if brain_linked_landing else None
    walking_control = None
    walking_reference = None
    safety_reason = None
    fallen_since = None
    walking_samples = []
    reference_height=.1278
    initial_position=[value*.1 for value in habitat.spawn_position_mm] if habitat.spawn_position_mm is not None else None
    if initial_position is not None:
        reference_height=initial_position[2]
    try:
        paths = prepare_data(data_dir)
        env = create_environment(habitat, 3600, wing_pattern=paths["wing_pattern_fmech.npy"], interactive=True,
                                 fluid_physics=fluid_physics,initial_position=initial_position)
        with ExitStack() as resources:
            resources.callback(env.close)
            timestep = env.reset()
            model, data = env.physics.model.ptr, env.physics.data.ptr
            body = model.body("walker/thorax").id
            ground = model.geom("groundplane").id
            finger_body = model.body("virtual_finger").id
            mocap = model.body_mocapid[finger_body]
            finger_geom = model.geom("virtual_finger_tip").id
            marker = model.geom("pointer_target").id
            eye_ids = [model.camera("walker/eye_left").id, model.camera("walker/eye_right").id]
            for geom in range(model.ngeom):
                if (mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom) or "").startswith("walker"):
                    model.geom_group[geom] = 1
            for item in objects.placements:
                set_flight_object_position(model,data,item["name"],item["position_mm"])
            mj.mj_forward(model,data)
            original_friction = model.geom_friction[ground].copy()
            mass = float(sum(model.body_mass[i] for i in range(model.nbody)
                             if (mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i) or "").startswith("walker")))
            initial_mass, initial_inertia = model.body_mass.copy(), model.body_inertia.copy()
            adapter = MotorAdapter(env)
            contact_reader = FlyContactReader(model, habitat)
            water = FluidPhysics(model,habitat,force_dt=CONTROL_DT) if fluid_physics else None
            walking = PublishedMotorPolicy(prepare_tflite_policy(data_dir, CATALOG, "walking"))
            flying = PublishedMotorPolicy(prepare_tflite_policy(data_dir, CATALOG, "flight"))
            brain = BrainClient(ROOT/".venv/bin/python", data_dir, output, food.seed, takeoff=True, telemetry=True,
                                graded_vision=graded_vision,dnp10_intervention=research_dnp10,
                                walking_readouts=walking_readouts or brain_guided_walking,
                                walking_control=brain_guided_walking,
                                walking_intervention=research_walking_control if research_walking_control != "motor-disconnect" else None)
            resources.callback(brain.close)
            extension = LegExtension(brain.metadata) if neural_leg_extension else None
            neural_landing=NeuralLanding(brain.metadata,arena_half_size_mm*.1,
                                         contact_stabilization=brain_guided_walking) if brain_linked_landing else None
            if walking_navigation is not None:
                walking_navigation.begin(data.xpos[body],0.)
            if brain_guided_walking:
                walking_control = WalkingControl(brain.metadata)
                walking_reference = WalkingReference()
                rotation=data.xmat[body].reshape(3,3)
                walking_reference.begin(data.xpos[body],0.,math.atan2(rotation[1,0],rotation[0,0]),height=reference_height)
            controller_scope = (
                "GF initiation; approved engineered orbit navigation and force-assisted landing (NOT biological)"
                if engineered_navigation else
                "GF-triggered assisted launch; learned straight-reference flight, not neural navigation"
            )
            if extension is not None:
                controller_scope += ". " + LEG_EXTENSION_SCOPE
            if avoidance is not None:
                controller_scope = "GF-triggered assisted launch. " + AVOIDANCE_SCOPE
                if extension is not None:
                    controller_scope += ". " + LEG_EXTENSION_SCOPE
            if neural_landing is not None:
                controller_scope += ". "+LANDING_SCOPE+". Ground boundary reference is engineered; walking policy is learned."
            if landing_surface_vision:
                controller_scope += ". Landing input uses assumed surface bounding silhouettes through LC4/LPLC2; natural DNp10 visual pathway is not calibrated."
            if walking_readouts and not brain_guided_walking:
                controller_scope += ". Walking/halting spikes are observed, not decoded into gait."
            if brain_guided_walking:
                controller_scope += ". "+WALK_SCOPE+". "+DRIVE_SCOPE
            eye_scope = "FlyBody rectilinear cameras; not FlyGym compound-eye sampling"
            if graded_vision:
                eye_scope += ". " + GRADED_ENCODER["scope"] + " Only physical spheres are encoded; not full optic flow."
            front_tibias = [model.joint(f"walker/tibia_T1_{side}").qposadr[0]
                            for side in ("left", "right")] if extension is not None or test_leg_extension else []
            front_tibia_actuators = [model.actuator(f"walker/tibia_T1_{side}").id
                                    for side in ("left", "right")] if front_tibias else []
            flight_test_sphere = None
            peak_flight_activation = 0.0
            flight_dn_spikes = 0
            (output/"brain-metadata.json").write_text(json.dumps(brain.metadata)+"\n")
            connections = ConnectionIndex(brain.metadata["connection_index_dir"], brain.metadata["neuron_ids"],
                                          brain.metadata["upstream_commit"])
            inputs = BrowserInputs()
            dashboard_metadata={**brain.metadata,"fly_count":1,
                                "independent_brains":[{"id":1,"seed":food.seed,"neurons":brain.metadata["neurons"]}]}
            app = resources.enter_context(Dashboard(output, dashboard_metadata, port=port, connections=connections, inputs=inputs))
            world = resources.enter_context(WorldRenderer(model, data, habitat.half_size_mm*.1, body, inputs,
                                                         app.publish_world, unit_scale=.1, initial_distance=1.2))
            eyes = resources.enter_context(mj.Renderer(model, height=256, width=256))
            eye_option = mj.MjvOption()
            eye_option.geomgroup[1] = 0
            eye_option.geomgroup[2] = 0
            log = resources.enter_context((output/"neural-flight.jsonl").open("x"))
            events = resources.enter_context((output/"app-events.jsonl").open("x"))
            target = np.array([0., 0, .15])
            finger = target.copy()
            cursor_valid = False
            looming = {eye: SphereLooming() for eye in eye_ids}
            sphere_vision = SphereVision() if graded_vision else None
            surface_vision = LandingSurfaceVision() if landing_surface_vision else None
            surface_ids=[model.geom(obj.name).id for obj in habitat.objects
                         if obj.name in {"fruit_food_surface","bark_landing_patch","stone_landing_surface",
                                         "wet_soil_patch","fallen_leaf_a","fallen_leaf_b","fallen_leaf_c"}]
            neural_response = None
            next_eyes = 0
            eye_time = None
            bump_until = 0
            last_pointer_wall = time.perf_counter()
            print(f"Single-body flight app: {app.url}", flush=True)
            (output/"status.json").write_text('{"status":"running"}\n')
            while not closed and (target_steps is None or total_steps < target_steps):
                world.check()
                while not inputs.empty():
                    event = inputs.get_nowait()
                    events.write(json.dumps({"time_s":total_steps*CONTROL_DT,"episode":episode,"input":event})+"\n")
                    events.flush()
                    error_message = None if not safety_stopped else safety_reason or "Boundary safety stop. Reset to restart."
                    if event["kind"]=="fly_count":
                        if controlled_test or seconds is not None:
                            error_message="Bounded validation locks fly population changes."
                        elif event["count"]!=1:
                            requested_fly_count=event["count"]
                            closed=True
                    elif event["kind"]=="inspect_fly":
                        if event["fly"]!=1:error_message="This episode contains only Fly1."
                    elif event["kind"] == "pointer":
                        position = world.target(event["x"]*1280, (1-event["y"])*960, plane_z=.15)
                        cursor_valid = position is not None
                        if cursor_valid:
                            target[:] = position
                            target[:2] = np.clip(target[:2], -habitat.half_size_mm*.1+.15, habitat.half_size_mm*.1-.15)
                    elif event["kind"] != "key":
                        controls["follow_camera"] = False
                    else:
                        key = event["key"]
                        if controlled_test and key not in {"Q","P","C"}:
                            error_message="Controlled test: physical edits, pushes and reset are disabled until this bounded run ends."
                            print(f"WARNING: controlled test rejected {key}",file=sys.stderr)
                            continue
                        if key == "Q":
                            closed = True
                        elif key == "P":
                            if safety_stopped:
                                error_message = "Safety stop requires an explicit Reset; resuming into a boundary is not allowed."
                            else:
                                controls["paused"] = not controls["paused"]
                        elif key == "R":
                            timestep = env.reset()
                            model, data = env.physics.model.ptr, env.physics.data.ptr
                            if model.body_mass.shape != initial_mass.shape or model.body_inertia.shape != initial_inertia.shape:
                                raise RuntimeError("Reset changed body structure; display state cannot be transferred")
                            adapter = MotorAdapter(env)
                            contact_reader = FlyContactReader(model, habitat)
                            water = FluidPhysics(model,habitat,force_dt=CONTROL_DT) if fluid_physics else None
                            for geom in range(model.ngeom):
                                if (mj.mj_id2name(model,mj.mjtObj.mjOBJ_GEOM,geom) or "").startswith("walker"):
                                    model.geom_group[geom]=1
                            neural_response = brain.reset()
                            if walking_control is not None:
                                walking_control.reset()
                                walking_samples = []
                                reference_height=initial_position[2] if initial_position is not None else .1278
                                rotation=data.xmat[body].reshape(3,3)
                                walking_reference.begin(data.xpos[body],0.,math.atan2(rotation[1,0],rotation[0,0]),height=reference_height)
                            if extension is not None:
                                extension.reset()
                            if neural_landing is not None:
                                neural_landing.reset()
                                walking_navigation.begin(data.xpos[body],0.)
                                neural_landing_handoffs=[]
                                release_position=None
                                post_release_displacement_mm=0.
                                maximum_post_release_landing_assistance=0.
                            flight_test_sphere = None
                            peak_flight_activation = 0.0
                            flight_dn_spikes = 0
                            episode += 1
                            episode_steps = 0
                            trigger_time = None
                            landed_at = None
                            landing_contacts = 0
                            post_landing_steps = 0
                            landing_motor = None
                            walk_motor = None
                            stable_post_landing_steps = 0
                            if engineered_navigation:
                                navigation=FlightNavigation(arena_half_size_mm*.1)
                            if avoidance is not None:
                                avoidance.reset()
                            minimum_flight_clearance_cm = None
                            minimum_flight_height_cm = None
                            minimum_flight_upright = None
                            safety_stopped = False
                            safety_reason = None
                            fallen_since = None
                            phase = "walking"
                            error_message = None
                            bump_until = 0
                            next_eyes = 0
                            eye_frames = None
                            eye_time = None
                            last_pointer_wall = time.perf_counter()
                            for state in looming.values():
                                state.previous_angle = None
                            if sphere_vision is not None:
                                sphere_vision.reset()
                            if surface_vision is not None:
                                surface_vision.reset()
                            app.publish({**neural_response,"habitat_time_s":total_steps*CONTROL_DT,"status":"reset"})
                            for item in objects.placements:
                                set_flight_object_position(model,data,item["name"],item["position_mm"])
                            model.geom_friction[ground] = original_friction
                            if controls["slippery"]:
                                model.geom_friction[ground,0]=.1
                        elif key in {"H","T","F","C"}:
                            name = {"H":"finger_enabled","T":"sugar_enabled","F":"slippery","C":"follow_camera"}[key]
                            controls[name] = not controls[name]
                            if key == "H" and sphere_vision is not None:
                                sphere_vision.forget(finger_geom)
                            model.geom_friction[ground] = original_friction
                            if controls["slippery"]:
                                model.geom_friction[ground,0] = .1
                        elif key == "B":
                            bump_until = episode_steps*CONTROL_DT+.05
                        elif key in {"1","2","3"}:
                            try:
                                if key == "3":
                                    item = objects.remove()
                                    set_flight_object_position(model,data,item["name"])
                                else:
                                    if not cursor_valid:
                                        raise ValueError("Move over the ground world before placing an object")
                                    item = objects.place("box" if key=="1" else "sphere", (target*10).tolist())
                                    set_flight_object_position(model,data,item["name"],item["position_mm"])
                                mj.mj_forward(model,data)
                                if sphere_vision is not None:
                                    sphere_vision.forget(model.geom(item["name"]).id)
                                (output/"objects.json").write_text(json.dumps(objects.placements,indent=2)+"\n")
                            except ValueError as error:
                                error_message = str(error)
                                print(f"WARNING: object edit rejected: {error}", file=sys.stderr)
                        else:
                            error_message = f"{key} is not supported by the experimental flight backend."
                if closed:
                    break
                duration_steps = 50 if target_steps is None else min(50,target_steps-total_steps)
                duration = duration_steps*CONTROL_DT
                elapsed = episode_steps*CONTROL_DT
                pointer_wall_now = time.perf_counter()
                pointer_wall_duration = pointer_wall_now-last_pointer_wall
                last_pointer_wall = pointer_wall_now
                if test_approach:
                    controls["finger_enabled"] = True
                    target[:] = data.xpos[body]+data.xmat[body].reshape(3,3)@np.array([
                        max(.4, 2-8*max(0, elapsed-.12)),0,.2,
                    ])
                if test_leg_extension:
                    controls["finger_enabled"] = .75 <= elapsed < .93
                    if controls["finger_enabled"]:
                        if flight_test_sphere is None:
                            flight_test_sphere = data.xpos[body].copy()+np.array([4.,0,.05])
                        finger[:] = flight_test_sphere
                        target[:] = flight_test_sphere
                    data.mocap_pos[mocap] = finger if controls["finger_enabled"] else [0,0,-10]
                elif test_brain_landing:
                    controls["finger_enabled"]=1.2<=elapsed<1.5
                    if controls["finger_enabled"]:
                        if flight_test_sphere is None:
                            rotation=data.xmat[body].reshape(3,3)
                            heading=math.atan2(rotation[1,0],rotation[0,0])
                            flight_test_sphere=data.xpos[body].copy()+np.array([4*math.cos(heading),4*math.sin(heading),.05])
                        finger[:]=flight_test_sphere
                        target[:]=flight_test_sphere
                    data.mocap_pos[mocap]=finger if controls["finger_enabled"] else [0,0,-10]
                elif controls["finger_enabled"] and not controls["paused"] and not safety_stopped:
                    if test_approach:
                        delta = target-finger
                        distance = np.linalg.norm(delta)
                        finger[:] += delta*min(1, 2*duration/distance) if distance else 0
                    else:
                        finger[:] = np.array(capped_motion((finger*10).tolist(), (target*10).tolist(),
                                                          pointer_wall_duration))*.1
                    data.mocap_pos[mocap] = finger
                else:
                    data.mocap_pos[mocap] = [0,0,-10]
                model.geom_pos[marker] = target
                model.geom_rgba[marker,3] = 1 if cursor_valid else 0
                mj.mj_forward(model,data)
                if controls["paused"] or safety_stopped:
                    if neural_response is not None:
                        app.publish({**neural_response,"status":"safety stopped" if safety_stopped else "paused",
                                     "paused":True,"habitat_time_s":total_steps*CONTROL_DT,
                                     "environment_controls":{**controls,"paused":True},"editable_objects":len(objects.placements),
                                     "virtual_finger_available":True,"interaction_error":error_message,"motor_phase":phase,
                                     "safety_notice":safety_reason or "Boundary safety pause: app remains open; camera/neural inspection available. Reset to restart." if safety_stopped else None,
                                     "controller_scope":controller_scope,
                                     "controlled_test_inputs":controlled_test,
                                     **({"leg_extension":extension.snapshot()} if extension is not None else {}),
                                     **({"brain_linked_landing":neural_landing.snapshot()} if neural_landing is not None else {}),
                                     **({"walking_control":walking_control.snapshot()} if walking_control is not None else {}),
                                     "movable_objects":contact_reader.movable_snapshot(data),
                                     "water":water.snapshot() if water is not None else
                                         {"surface_mode":"rigid-prototype","scope":"Water-colored fixed collision surface; no fluid forces or swimming."},
                                     "eye_scope":eye_scope})
                    world.submit(model,data,total_steps*CONTROL_DT,controls["follow_camera"])
                    time.sleep(.02)
                    continue
                rates = None
                if sphere_vision is not None:
                    sources = [{"geom_id":finger_geom,"name":"virtual_finger_tip",
                                "enabled":controls["finger_enabled"]}]
                    for name in ([obj.name for obj in (*habitat.objects,*habitat.movable_objects) if obj.kind == "sphere"]
                                 + [obj["name"] for obj in objects.placements if obj["kind"] == "sphere"]):
                        sources.append({"geom_id":model.geom(name).id,"name":name,"enabled":True})
                    features = sphere_vision.sample(model,data,sources,eye_ids,body,duration)
                    rates = graded_visual_rates(features)
                    stimulus = any(rates.values())
                else:
                    views = finger_visibility(model,data,finger_geom,finger,.15,eye_ids,body) if controls["finger_enabled"] else []
                    by_eye = {v["camera_id"]:v for v in views}
                    features = []
                    for eye,state in looming.items():
                        view = by_eye.get(eye)
                        feature = state.sample(view["distance_mm"]*10 if view else 1000,1.5,duration,
                                               controls["finger_enabled"],view["visible"] if view else False)
                        features.append(feature)
                    stimulus = any(f["looming_active"] for f in features)
                if surface_vision is not None:
                    surface_features=surface_vision.sample(model,data,surface_ids,eye_ids,body,duration,
                                                          phase=="flight")
                    features.extend(surface_features)
                    stimulus = stimulus or any(f["looming_active"] for f in surface_features)
                if test_stimulus:
                    launch_stimulus = .3 <= elapsed < .4
                    stimulus = stimulus or launch_stimulus if test_leg_extension or test_brain_landing or surface_vision is not None else launch_stimulus
                    if graded_vision and (launch_stimulus or not (test_leg_extension or test_brain_landing)):
                        rates = {"LC4":100. if launch_stimulus else 0.,
                                 "LPLC2":100. if launch_stimulus else 0.}
                probe = (data.xpos[body]+data.xmat[body].reshape(3,3)@np.array(food.probe_mm)*.1)*10
                exposure = food.exposure(probe.tolist(),controls["sugar_enabled"])
                walking_rates = None
                walking_cues = None
                if walking_control is not None:
                    ground_phase = phase in {"walking","post-landing-walk","landing-release"}
                    walking_rates, walking_cues = scene_drive(model,data,body,arena_half_size_mm*.1,ground_phase)
                    if test_walking_control:
                        walking_rates = prescribed_drive(elapsed)
                        walking_cues = {"scope":"Explicit bounded upstream neural input profile, not environment sensing"}
                brain.begin_step(duration*1000,exposure["sugar_contact"],stimulus,visual_rates_Hz=rates,
                                 walking_drive_Hz=walking_rates)
                neural_response = brain.finish_step()
                if avoidance is not None and trigger_time is not None and (neural_landing is None or neural_landing.request_time is None):
                    avoidance.update(data.xpos[body],elapsed,obstacle_samples(model,data,body,avoidance.known_obstacle_ids))
                for tick in range(duration_steps):
                    elapsed = episode_steps*CONTROL_DT
                    phase = "walking" if trigger_time is None else "assisted-launch" if elapsed-trigger_time<.3 else "flight"
                    if neural_landing is not None and neural_landing.request_time is not None and trigger_time is not None:
                        phase=neural_landing.phase(elapsed)
                    if navigation is not None and trigger_time is not None:
                        if elapsed-trigger_time>=1.3 or any(abs(x)>=habitat.half_size_mm*.1-2 for x in data.xpos[body,:2]):
                            navigation.request_landing(data.xpos[body],elapsed)
                        if navigation.landing_start is not None:
                            phase="assisted-landing" if landed_at is None else "post-landing-walk"
                    data.xfrc_applied.fill(0)
                    landing_force=np.zeros(6)
                    if walking_control is not None:
                        neural_speed, neural_turn = walking_control.advance(CONTROL_DT)
                        if research_walking_control == "motor-disconnect":
                            neural_speed = neural_turn = 0.
                    if neural_landing is not None and neural_landing.request_time is not None and trigger_time is not None:
                        action,landing_motor=neural_landing.motor_action(
                            adapter,walking,flying,timestep.observation,elapsed,
                            None if episode_steps%WALK_EVERY==0 else landing_motor)
                        velocity=np.zeros(6)
                        mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                        landing_force=neural_landing.assistance(
                            mass,elapsed,data.xpos[body],velocity,data.xmat[body].reshape(3,3))
                        data.xfrc_applied[body]=landing_force
                    elif trigger_time is None or landed_at is not None:
                        walk_reference=walking_navigation
                        if walking_control is not None:
                            if habitat.schema_version>=4 and episode_steps%WALK_EVERY==0:
                                reference_height=.1278+support_height(model,data,body)
                            walking_reference.update(data.xpos[body],elapsed,neural_speed,neural_turn,height=reference_height)
                            walk_reference = walking_reference
                        elif neural_landing is not None and neural_landing.touchdown_time is not None:
                            walk_reference=neural_landing.walk_navigation
                        elif walking_navigation is not None:
                            walking_navigation.update(data.xpos[body],elapsed)
                        if episode_steps % WALK_EVERY == 0 or walk_motor is None or landed_at is not None and post_landing_steps==0:
                            walk_motor,_ = walking.action(adapter.walking_observation(timestep.observation,2,navigation=walk_reference),
                                                     adapter.projections["walking"]["spec"])
                        action = adapter.walking_action(walk_motor)
                        if engineered_navigation and landed_at is not None and elapsed-landed_at<.5:
                            velocity=np.zeros(6)
                            mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                            desired=[env.task.walk_origin[0]+2*(elapsed-landed_at),env.task.walk_origin[1],.1278]
                            scale=max(0,1-(elapsed-landed_at)/.5)
                            data.xfrc_applied[body]=scale*landing_assistance(
                                mass,data.xpos[body],velocity,data.xmat[body].reshape(3,3),desired)
                    else:
                        motor,_ = flying.action(adapter.flight_observation(timestep.observation,
                                                                          navigation=avoidance or navigation),
                                               adapter.projections["flight"]["spec"])
                        action = adapter.flight_action(motor)
                        if phase=="assisted-landing":
                            if episode_steps % WALK_EVERY==0 or landing_motor is None:
                                env.task.walk_origin=np.array(navigation.landing_origin)
                                env.task.walk_start=env.physics.time()
                                landing_motor,_=walking.action(
                                    adapter.walking_observation(timestep.observation,0),
                                    adapter.projections["walking"]["spec"])
                            action=adapter.walking_action(landing_motor)
                            velocity=np.zeros(6)
                            mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                            desired=navigation.reference(elapsed)[0]
                            data.xfrc_applied[body]=landing_assistance(
                                mass,data.xpos[body],velocity,data.xmat[body].reshape(3,3),desired)
                            data.xfrc_applied[body,3:]*=min(1,(elapsed-navigation.landing_start)/.2)
                        if phase == "assisted-launch":
                            velocity = np.zeros(6)
                            mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                            quat = np.array([math.cos(math.radians(47.5)/2),0,-math.sin(math.radians(47.5)/2),0])
                            if avoidance is not None:
                                from flybody.quaternions import mult_quat
                                desired,desired_velocity,yaw = avoidance.reference(elapsed)
                                quat = mult_quat(np.array([math.cos(yaw/2),0,0,math.sin(yaw/2)]),quat)
                            rotation = np.zeros(9)
                            mj.mju_quat2Mat(rotation,quat)
                            origin = env.task.launch_origin
                            if avoidance is None:
                                desired = np.array([origin[0]+20*(elapsed-trigger_time),origin[1],1])
                            data.xfrc_applied[body] = assisted_force(mass,data.xpos[body],velocity,
                                                                   data.xmat[body].reshape(3,3),rotation.reshape(3,3),desired,
                                                                   desired_velocity if avoidance is not None else None)
                    if extension is not None:
                        activation = extension.advance(CONTROL_DT, phase == "flight")
                        if phase == "flight":
                            action = adapter.leg_extension_action(action, activation)
                            peak_flight_activation = max(peak_flight_activation, activation)
                    if neural_landing is not None:
                        neural_landing.decoder.advance(CONTROL_DT,phase=="flight")
                    body_velocity = np.zeros(6)
                    mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,body_velocity,False)
                    wind = habitat.wind_force((body_velocity[3:]*10).tolist())
                    data.xfrc_applied[body,:3] += np.array(wind)*.1
                    if elapsed < bump_until:
                        data.xfrc_applied[body,1] += .5
                    if water is not None:
                        water.apply(data)
                    timestep = env.step(action.copy())
                    episode_steps += 1
                    total_steps += 1
                    if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                        raise RuntimeError("Unified app physical state became nonfinite")
                    contacts = contact_reader.sample(data)
                    if neural_landing is not None and neural_landing.request_time is not None:
                        velocity=np.zeros(6)
                        mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                        neural_landing.observe(episode_steps*CONTROL_DT,contacts,
                                               float(data.xmat[body].reshape(3,3)[2,2]),
                                               float(np.linalg.norm(velocity[3:])),data.xpos[body])
                        stable_post_landing_steps=neural_landing.stable_walk_steps
                        if neural_landing.touchdown_time is not None:
                            landed_at=neural_landing.touchdown_time
                        if neural_landing.release_time is not None and episode_steps*CONTROL_DT>=neural_landing.release_time:
                            if trigger_time is not None:
                                walk_motor=None
                                release_position=data.xpos[body].copy()
                                if walking_reference is not None:
                                    rotation=data.xmat[body].reshape(3,3)
                                    reference_height=.1278+support_height(model,data,body) if habitat.schema_version>=4 else .1278
                                    walking_reference.begin(data.xpos[body],episode_steps*CONTROL_DT,
                                                            math.atan2(rotation[1,0],rotation[0,0]),height=reference_height)
                            trigger_time=None
                            post_landing_steps+=1
                            if release_position is not None:
                                post_release_displacement_mm=float(np.linalg.norm(data.xpos[body,:2]-release_position[:2]))*10
                            if elapsed>=neural_landing.release_time:
                                maximum_post_release_landing_assistance=max(maximum_post_release_landing_assistance,
                                                                           float(np.max(np.abs(landing_force))))
                    if phase=="walking":
                        initial_contact |= contacts>0
                        if walking_control is not None:
                            upright=float(data.xmat[body].reshape(3,3)[2,2])
                            if upright < .5 and contacts > 0:
                                fallen_since=episode_steps*CONTROL_DT if fallen_since is None else fallen_since
                                if episode_steps*CONTROL_DT-fallen_since >= .15:
                                    safety_stopped = True
                                    safety_reason = "Fallen-state safety pause: not biological death. Camera/neural inspection remains available; Reset required. No pose recovery is fabricated."
                            else:
                                fallen_since=None
                    if phase=="flight":
                        flight_steps += 1
                        floor_contact_steps += int(contacts>0)
                        clearance = habitat.half_size_mm*.1-max(abs(x) for x in data.xpos[body,:2])
                        height = float(data.xpos[body,2])
                        upright = float(data.xmat[body].reshape(3,3)[2,2])
                        minimum_flight_clearance_cm = clearance if minimum_flight_clearance_cm is None else min(minimum_flight_clearance_cm,clearance)
                        minimum_flight_height_cm = height if minimum_flight_height_cm is None else min(minimum_flight_height_cm,height)
                        minimum_flight_upright = upright if minimum_flight_upright is None else min(minimum_flight_upright,upright)
                    if phase=="assisted-landing":
                        upright=float(data.xmat[body].reshape(3,3)[2,2])
                        velocity=np.zeros(6)
                        mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                        landing_contacts=landing_contacts+1 if contacts>0 and upright>.8 and np.linalg.norm(velocity[3:])<5 else 0
                        if landing_contacts>=250 and elapsed-navigation.landing_start>=1.2:
                            landed_at=episode_steps*CONTROL_DT
                            env.task.walk_origin=env.task.walker.get_pose(env.physics)[0].copy()
                            env.task.walk_start=env.physics.time()
                    elif engineered_navigation and phase=="post-landing-walk":
                        post_landing_steps+=1
                        if elapsed-landed_at>=.5:
                            stable_post_landing_steps=stable_post_landing_steps+1 if float(data.xmat[body].reshape(3,3)[2,2])>.8 else 0
                    if timestep.last():
                        raise RuntimeError("Unified task terminated; no automatic physics reset was performed")
                if abs(neural_response["brain_time_ms"]-episode_steps*CONTROL_DT*1000)>1e-5:
                    raise RuntimeError("Unified app brain/body clocks diverged")
                if walking_control is not None:
                    walking_control.accept(neural_response)
                    rotation=data.xmat[body].reshape(3,3)
                    if test_walking_control:
                        walking_samples.append({
                            "time_s":episode_steps*CONTROL_DT,"position_cm":data.xpos[body].tolist(),
                            "yaw_rad":math.atan2(rotation[1,0],rotation[0,0]),
                            "upright_cosine":float(rotation[2,2]),
                            "speed_cm_s":walking_control.speed,"turn_rad_s":walking_control.turn,
                            "motor_speed_cm_s":walking_reference.speed,"motor_turn_rad_s":walking_reference.turn,
                        })
                if extension is not None:
                    extension.accept(neural_response)
                if neural_landing is not None:
                    rotation=data.xmat[body].reshape(3,3)
                    velocity=np.zeros(6)
                    mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,body,velocity,False)
                    before_pos,before_vel=data.qpos.copy(),data.qvel.copy()
                    requested=neural_landing.accept(neural_response,phase=="flight",data.xpos[body],velocity[3:],
                                                    math.atan2(rotation[1,0],rotation[0,0]))
                    if requested:
                        neural_landing_handoffs.append({
                            **neural_landing.request,
                            "qpos_preserved":bool(np.array_equal(before_pos,data.qpos)),
                            "qvel_preserved":bool(np.array_equal(before_vel,data.qvel))})
                        landing_motor=None
                if phase == "flight":
                    flight_dn_spikes += sum(neural_response["sensorimotor_spikes"][value]
                                            for value in DNP10_IDS.values())
                if trigger_time is None and not safety_stopped and sum(neural_response["giant_fiber_spikes"].values())>0:
                    if neural_landing is not None and neural_landing.request_time is not None:
                        neural_landing.reset(clear_neural=False)
                        landed_at=None
                        landing_motor=None
                    before_pos,before_vel = data.qpos.copy(),data.qvel.copy()
                    env.task.begin_launch(env.physics)
                    trigger_time = episode_steps*CONTROL_DT
                    handoff = {"episode":episode,"time_s":trigger_time,
                               "qpos_preserved":bool(np.array_equal(before_pos,data.qpos)),
                               "qvel_preserved":bool(np.array_equal(before_vel,data.qvel))}
                    if not handoff["qpos_preserved"] or not handoff["qvel_preserved"]:
                        raise RuntimeError("Flight handoff modified physical state")
                    handoffs.append(handoff)
                    if navigation is not None:
                        navigation.begin(env.task.launch_origin,trigger_time)
                    if avoidance is not None:
                        rotation=data.xmat[body].reshape(3,3)
                        avoidance.begin(env.task.launch_origin,trigger_time,
                                        math.atan2(rotation[1,0],rotation[0,0]),launch=True)
                if any(abs(x*10)>=habitat.half_size_mm-5 for x in data.xpos[body,:2]):
                    safety_stopped = True
                    safety_reason = "Boundary safety pause: app remains open; Reset required."
                    error_message = safety_reason
                new_eyes = None
                if elapsed>=next_eyes:
                    images=[]
                    for eye in eye_ids:
                        eyes.update_scene(data,eye,scene_option=eye_option)
                        images.append(eyes.render())
                    new_eyes=np.concatenate(images,axis=1)
                    eye_frames=new_eyes
                    eye_count += 1
                    next_eyes=elapsed+.1
                    eye_time=total_steps*CONTROL_DT
                packet={**neural_response,"habitat_time_s":total_steps*CONTROL_DT,
                        **({"eye_time_s":eye_time} if eye_time is not None else {}),
                        "status":"fallen" if safety_stopped and fallen_since is not None else "safety stopped" if safety_stopped else phase,"paused":safety_stopped,
                        "environment_controls":{**controls,"paused":controls["paused"] or safety_stopped},
                        "editable_objects":len(objects.placements),"virtual_finger_available":True,
                        "interaction_error":error_message,"motor_phase":phase,
                        "safety_notice":safety_reason or "Boundary safety stop. Reset to restart." if safety_stopped else None,
                        "finger_position_mm":(finger*10).tolist(),"pointer_target_mm":(target*10).tolist(),
                        "pointer_lag_mm":float(np.linalg.norm(target-finger)*10),
                        "finger_motion_clock":"stationary world sphere (explicit flight leg test)" if test_leg_extension else "simulated time (prescribed test)" if test_approach else "wall time (external interaction)",
                        "finger_wall_duration_s":min(pointer_wall_duration,.1),
                        "controller_scope":controller_scope,
                        "movable_objects":contact_reader.movable_snapshot(data),
                        "water":water.snapshot() if water is not None else
                            {"surface_mode":"rigid-prototype","scope":"Water-colored fixed collision surface; no fluid forces or swimming."},
                        **({"flight_avoidance":avoidance.snapshot()} if avoidance is not None else {}),
                        **({"leg_extension":extension.snapshot()} if extension is not None else {}),
                        **({"brain_linked_landing":neural_landing.snapshot()} if neural_landing is not None else {}),
                        **({"walking_control":walking_control.snapshot(),"walking_drive_Hz":walking_rates,
                            "walking_drive_cues":walking_cues,
                            "walking_body_yaw_rad":math.atan2(rotation[1,0],rotation[0,0]),
                            "walking_motor_reference":{"speed_cm_s":walking_reference.speed,
                                                       "turn_rad_s":walking_reference.turn}} if walking_control is not None else {}),
                        **({"front_tibia_rad":data.qpos[front_tibias].tolist(),
                            "front_tibia_actuator_force":data.actuator_force[front_tibia_actuators].tolist()}
                           if front_tibias else {}),
                        "eye_scope":eye_scope}
                app.publish(packet,new_eyes)
                world.submit(model,data,total_steps*CONTROL_DT,controls["follow_camera"])
                log.write(json.dumps({"packet":packet,"exposure":exposure,"looming":features,
                                      "test_stimulus":test_stimulus,"position_cm":data.xpos[body].tolist(),
                                      "upright_cosine":float(data.xmat[body].reshape(3,3)[2,2]),
                                      "floor_contacts":contacts,
                                      "landing_assistance_force_torque":landing_force.tolist(),
                                      "external_force_torque":data.xfrc_applied[body].tolist(),
                                      **({"qpos_sha256":hashlib.sha256(data.qpos.tobytes()).hexdigest(),
                                          "qvel_sha256":hashlib.sha256(data.qvel.tobytes()).hexdigest(),
                                          "action_sha256":hashlib.sha256(action.tobytes()).hexdigest()}
                                         if test_walking_control else {})})+"\n")
                log.flush()
                if safety_stopped and target_steps is not None:
                    break
            unchanged=np.array_equal(initial_mass,model.body_mass) and np.array_equal(initial_inertia,model.body_inertia)
            if not unchanged:
                raise RuntimeError("Unified app body mass/inertia changed during a controller transition")
            summary={"status":"reconfigure_requested" if requested_fly_count is not None else "closed_by_user" if closed else "safety_stopped" if safety_stopped else "completed","backend":"single-body FlyBody",
                     "fly_count":1,"requested_fly_count":requested_fly_count,
                     "same_body_mass_inertia_unchanged":bool(unchanged),"seconds":total_steps*CONTROL_DT,
                     "handoffs":handoffs,"flight_steps":flight_steps,"flight_floor_contact_steps":floor_contact_steps,
                     "safety_stopped":safety_stopped,"eye_frames":eye_count,"test_stimulus":test_stimulus,
                     "test_approach":test_approach,
                     "test_leg_extension":test_leg_extension,
                     "flight_dnp10_spikes":flight_dn_spikes,
                     "peak_flight_leg_activation":peak_flight_activation,
                     "initial_ground_contact_observed":bool(initial_contact),
                     "neural_motor_decoding":neural_leg_extension or brain_guided_walking,
                     "neural_motor_decoding_scope":". ".join(scope for enabled,scope in
                         ((neural_leg_extension,LEG_EXTENSION_SCOPE),(brain_guided_walking,WALK_SCOPE)) if enabled)
                         if neural_leg_extension or brain_guided_walking else "No neural leg decoder; learned motor comparisons",
                     "calibrated_vnc_muscle_decoding":False,
                     "landing_controller_enabled":engineered_navigation or brain_linked_landing,
                     "brain_linked_landing_enabled":brain_linked_landing,
                     "neural_landing_handoffs":neural_landing_handoffs,
                     "post_release_displacement_mm":post_release_displacement_mm,
                     "maximum_post_release_landing_assistance":maximum_post_release_landing_assistance,
                     "test_brain_landing":test_brain_landing,
                     "controlled_test_inputs":controlled_test,
                     "landing_surface_vision_enabled":landing_surface_vision,
                     "research_dnp10_intervention":research_dnp10,
                     "reduced_neural_leg_extension_enabled":neural_leg_extension,
                     "graded_vision_enabled":graded_vision,
                     "walking_readouts_enabled":walking_readouts or brain_guided_walking,
                     "brain_guided_walking_enabled":brain_guided_walking,
                     "walking_control":walking_control.snapshot() if walking_control is not None else None,
                     "walking_research_intervention":research_walking_control,
                     "safety_reason":safety_reason,
                     "walking_module_sha256":hashlib.sha256((ROOT/"scripts/fly_brain_walk.py").read_bytes()).hexdigest() if brain_guided_walking else None,
                     "flight_avoidance_enabled":flight_avoidance,
                     "habitat_width_mm":2*habitat.half_size_mm,
                     "habitat_static_objects":len(habitat.objects),
                     "habitat_materials":len(habitat.materials),
                     "movable_objects":contact_reader.movable_snapshot(data),
                     "fluid_physics_enabled":fluid_physics,"water_scope":WATER_SCOPE if fluid_physics else
                         "Water-colored fixed collision prototype; not fluid physics.",
                     "water_module_sha256":hashlib.sha256((ROOT/"scripts/fly_water.py").read_bytes()).hexdigest() if fluid_physics else None,
                     "water":water.snapshot() if water is not None else None,
                     "minimum_flight_boundary_clearance_cm":minimum_flight_clearance_cm,
                     "minimum_flight_height_cm":minimum_flight_height_cm,
                     "minimum_flight_upright_cosine":minimum_flight_upright,
                     **({"flight_avoidance":avoidance.snapshot()} if avoidance is not None else {}),
                     **({"graded_visual_encoder":GRADED_ENCODER} if graded_vision else {}),
                     **({"leg_extension":extension.snapshot()} if extension is not None else {}),
                     **({"brain_linked_landing":neural_landing.snapshot()} if neural_landing is not None else {}),
                     "landing_validated":False,
                     "landed_at_s":landed_at,"post_landing_steps":post_landing_steps,
                     "stable_unassisted_post_landing_steps":stable_post_landing_steps,
                     "engineered_navigation":engineered_navigation,"wall_seconds":time.perf_counter()-started}
            summary["source_script_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            summary["neural_worker_sha256"]=hashlib.sha256((ROOT/"scripts/fly_brain_worker.py").read_bytes()).hexdigest()
            summary["navigation_module_sha256"]=hashlib.sha256((ROOT/"scripts/fly_navigation.py").read_bytes()).hexdigest()
            if extension is not None:
                summary["leg_extension_module_sha256"]=hashlib.sha256((ROOT/"scripts/fly_leg_extension.py").read_bytes()).hexdigest()
            if graded_vision:
                summary["visual_encoder_sha256"]=hashlib.sha256((ROOT/"scripts/fly_looming.py").read_bytes()).hexdigest()
            if avoidance is not None:
                summary["avoidance_module_sha256"]=hashlib.sha256((ROOT/"scripts/fly_flight_avoidance.py").read_bytes()).hexdigest()
            if neural_landing is not None:
                summary["neural_landing_module_sha256"]=hashlib.sha256((ROOT/"scripts/fly_neural_landing.py").read_bytes()).hexdigest()
            if test_stimulus or test_approach:
                summary["flight_test_passed"]=bool(flight_test_passed(summary))
                if engineered_navigation:
                    summary["cycle_test_passed"]=bool(cycle_test_passed(summary))
                    summary["landing_validated"]=summary["cycle_test_passed"]
                if avoidance is not None:
                    summary["avoidance_test_passed"] = (
                        summary["flight_test_passed"] and minimum_flight_clearance_cm > .5
                        and minimum_flight_height_cm > .5 and minimum_flight_upright > .4
                        and avoidance.commands > 0)
                if test_brain_landing or landing_surface_vision and seconds>=6 and research_dnp10!="silence":
                    summary["brain_linked_cycle_test_passed"]=(
                        cycle_test_passed(summary) and bool(neural_landing_handoffs)
                        and all(h["qpos_preserved"] and h["qvel_preserved"] for h in neural_landing_handoffs)
                        and neural_landing.release_time is not None
                        and post_release_displacement_mm>=1. and maximum_post_release_landing_assistance==0.)
                    summary["landing_validated"]=summary["brain_linked_cycle_test_passed"]
                if research_dnp10=="silence":
                    summary["neural_landing_control_passed"]=(
                        not neural_landing_handoffs and neural_landing.decoder.total_spikes==0)
            if test_walking_control:
                summary["walking_control_profile"] = profile_metrics(walking_samples,research_walking_control)
                summary["walking_control_test_passed"] = (
                    summary["walking_control_profile"]["passed"] and not safety_stopped
                    and not handoffs and summary["same_body_mass_inertia_unchanged"])
            (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status":summary["status"]})+"\n")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status":"failed","error":str(error)})+"\n")
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--scene",type=Path,default=ROOT/"experiments/fly-walking/puddle-compact-habitat.json")
    parser.add_argument("--feeding-config",type=Path)
    parser.add_argument("--objects",type=Path)
    parser.add_argument("--seconds",type=float)
    parser.add_argument("--dashboard-port",type=int,choices=[DEFAULT_PORT],default=DEFAULT_PORT,
                        help="Single fixed browser-app port; no alternate-port or ephemeral fallback")
    parser.add_argument("--arena-half-size-mm",type=float,default=112.5/math.sqrt(2))
    parser.add_argument("--test-stimulus",action="store_true",help="Explicit bounded Poisson input test, not an environmental approach")
    parser.add_argument("--test-approach",action="store_true",help="Explicit bounded physical approaching-finger test through eye visibility")
    parser.add_argument("--engineered-navigation",action="store_true",help="Explicitly approved orbit navigation and force-assisted landing; not neural decoding")
    parser.add_argument("--neural-leg-extension",action="store_true",
                        help="Actual DNp10-driven reduced VNC/leg-actuator surrogate; not measured physiology or touchdown")
    parser.add_argument("--test-leg-extension",action="store_true",
                        help="Bounded stationary looming sphere during flight; requires --test-stimulus and >=1.2 s")
    parser.add_argument("--graded-vision",action="store_true",
                        help="Continuous physical sphere size/velocity encoder; explicit assumptions, not fitted physiology")
    parser.add_argument("--flight-avoidance",action="store_true",
                        help="Engineered predictive arena/obstacle turns through learned wings; not organic neural flight")
    parser.add_argument("--brain-linked-landing",action="store_true",
                        help="Actual DNp10 initiated assumed assisted landing cycle and engineered walking-boundary reference")
    parser.add_argument("--test-brain-landing",action="store_true",
                        help="Bounded upstream takeoff input then physical looming object; tests actual-DN initiated landing")
    parser.add_argument("--landing-surface-vision",action="store_true",
                        help="Assumed physical-surface looming input to existing visual network, only during flight")
    parser.add_argument("--research-dnp10",choices=["silence","sham"],
                        help="Explicit bounded neural causal intervention, not a normal browser control")
    parser.add_argument("--controlled-test",action="store_true",
                        help="Bounded stimulus validation: reject physical edits/pushes/reset; camera, pause and stop remain available")
    parser.add_argument("--walking-readouts",action="store_true",
                        help="Observe 28 primary-verified walking/halting cells; walking remains learned")
    parser.add_argument("--brain-guided-walking",action="store_true",
                        help="Opt-in modeled BPN/P9/FG drive and genuine speed/turn readouts through learned legs")
    parser.add_argument("--test-walking-control",action="store_true",
                        help="Bounded upstream walking/turning/stopping neural input profile,>=5s")
    parser.add_argument("--research-walking-control",choices=("sham","source-cut","output-silence","motor-disconnect"),
                        help="Bounded causal control, never a normal browser control")
    parser.add_argument("--fluid-physics",action="store_true",
                        help="Experimental bounded buoyancy/drag; replaces rigid water collision, not CFD or swimming")
    parser.add_argument("--fly-count",type=int,choices=(1,2,3),default=1,
                        help="Independent brains/bodies; changing through browser starts a new episode")
    parser.add_argument("--actuator-recovery",action=argparse.BooleanOptionalAction,default=False,
                        help="Experimental leg-only righting; failed fly becomes passive without stopping peers")
    args=parser.parse_args()
    if args.feeding_config is None:
        args.feeding_config=default_feeding_config(args.scene)
    try:
        count=args.fly_count
        output=args.output_dir
        objects=args.objects
        reconfiguration=0
        while True:
            if count==1 and not args.actuator_recovery:
                summary=run(args.data_dir,output,args.scene,args.feeding_config,objects,args.seconds,
                            args.dashboard_port,args.arena_half_size_mm,args.test_stimulus,args.test_approach,args.engineered_navigation,
                            args.neural_leg_extension,args.test_leg_extension,args.graded_vision,args.flight_avoidance,
                            args.brain_linked_landing,args.test_brain_landing,args.landing_surface_vision,args.research_dnp10,
                            args.controlled_test,args.walking_readouts,args.brain_guided_walking,
                            args.test_walking_control,args.research_walking_control,args.fluid_physics)
            else:
                if any((args.graded_vision,args.test_stimulus,args.test_approach,args.engineered_navigation,
                        args.test_leg_extension,args.test_brain_landing,args.research_dnp10,
                        args.test_walking_control,args.research_walking_control)):
                    raise ValueError("Multi-fly mode does not support single-fly graded/research probes; use physical sensory inputs")
                from fly_multi_app import run as run_multi
                summary=run_multi(args.data_dir,output,args.scene,args.feeding_config,objects,args.seconds,
                    args.dashboard_port,args.arena_half_size_mm,count,args.brain_guided_walking,args.flight_avoidance,
                    args.neural_leg_extension,args.brain_linked_landing,args.landing_surface_vision,args.fluid_physics,
                    args.controlled_test,actuator_recovery=args.actuator_recovery)
            requested=summary.get("requested_fly_count")
            if requested is None:break
            if args.seconds is not None:
                raise ValueError("Bounded runs cannot restart through population controls")
            reconfiguration+=1
            objects=output/"objects.json"
            output=args.output_dir/f"fly-count-episode-{reconfiguration:03d}"
            count=requested
            print(f"Starting explicit new episode with{count} independent flies; preserved objects:{objects}",flush=True)
    except (OSError,ValueError,RuntimeError,ImportError) as error:
        print(f"ERROR: experimental flight app failed: {error}",file=sys.stderr)
        return 1
    if any(summary.get(key) is False for key in ("flight_test_passed","cycle_test_passed","avoidance_test_passed",
                                                "brain_linked_cycle_test_passed","neural_landing_control_passed","walking_control_test_passed")):
        print("ERROR: requested flight/cycle test failed; inspect saved summary",file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    sys.exit(main())
