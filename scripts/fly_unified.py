"""Single-body legs-and-wings motor integration; explicitly learned controllers."""

import argparse
import hashlib
import json
import math
import sys
import queue
import time
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

from datasets import CATALOG, ROOT
from fly_environment import Environment, environment_dict
from fly_flight import prepare_data
from fly_flight_arena import make_arena
from fly_policy import PublishedMotorPolicy, prepare_policy
from fly_feeding import BrainClient
from fly_takeoff import assisted_force
from fly_graphics import ObserverScene
from sim_viewer import managed_viewer, ViewerStateGuard
from sim_units import simulation_steps


CONTROL_DT = 0.0002
WALK_EVERY = 10


def named_indices(available, required):
    if len(set(available)) != len(available) or len(set(required)) != len(required):
        raise ValueError("Motor channel names must be unique")
    mapping = {name: index for index, name in enumerate(available)}
    if any(name not in mapping for name in required):
        raise ValueError("Unified body is missing a published motor channel")
    return [mapping[name] for name in required]


def evaluate_motor(records, initial, final, upright, seconds, speed, airborne,
                   takeoff, landing, trigger_time, initial_contact, flight_steps,
                   flight_contacts, boundary_steps, landed_at, model_unchanged):
    minimum_upright = 0.4 if airborne else 0.8
    thresholds = {
        "minimum_upright_cosine": minimum_upright, "minimum_forward_fraction": 0.5,
        "maximum_position_error_cm": 0.15, "maximum_arena_exit_steps": 0,
    }
    if airborne:
        thresholds["maximum_flight_contact_steps"] = 0
    if takeoff:
        thresholds = {
            "initial_floor_contact": True, "minimum_post_assistance_flight_s": 0.5,
            "maximum_flight_contact_steps": 0, "maximum_arena_exit_steps": 0,
        }
        passed = (
            trigger_time is not None and initial_contact and flight_steps >= 2500
            and flight_contacts == 0 and boundary_steps == 0 and model_unchanged
        )
        if landing:
            thresholds.update({"minimum_post_landing_s": 0.3, "minimum_final_upright_cosine": 0.8})
            passed = passed and landed_at is not None and seconds - landed_at >= 0.3 and upright > 0.8
        else:
            thresholds["minimum_final_height_cm"] = 0.5
            passed = passed and final[2] > 0.5
    else:
        passed = (
            bool(records) and upright > minimum_upright
            and final[0] - initial[0] >= speed * seconds * 0.5
            and max(r["position_error_cm"] for r in records) <= 0.15
            and model_unchanged and boundary_steps == 0
            and (not airborne or flight_contacts == 0)
        )
    return bool(passed), thresholds


def create_environment(habitat, seconds, airborne=False, wing_pattern=None, interactive=False,
                       initial_heading=0., initial_wing_phase=.5, initial_position=None, fluid_physics=False,
                       fly_count=1):
    import numpy as np
    from dm_control import composer
    from flybody.fruitfly.fruitfly import FruitFly
    from flybody.tasks.base import Walking
    from flybody.tasks.constants import _WING_PARAMS
    if not math.isfinite(initial_heading) or not math.isfinite(initial_wing_phase) or not 0 <= initial_wing_phase < 1:
        raise ValueError("Diagnostic heading and wing phase must be finite; phase in [0,1)")
    if type(fly_count) is not int or not 1 <= fly_count <= 3 or fly_count>1 and airborne:
        raise ValueError("Shared habitat supports1..3 grounded-start fly bodies")

    class UnifiedTask(Walking):
        def __init__(self):
            arena=make_arena(habitat,fluid_physics=fluid_physics)
            self.habitat=habitat
            if interactive:
                from fly_objects import SLOTS
                finger=arena.mjcf_model.worldbody.add("body",name="virtual_finger",mocap=True,pos=[0,0,-10])
                finger.add("geom",name="virtual_finger_tip",type="sphere",size=[.15],rgba=[.85,.55,.4,1])
                finger.add("geom",name="virtual_finger_shaft",type="capsule",fromto=[0,0,.05,0,0,.5],
                           size=[.11],rgba=[.78,.48,.34,1],contype=0,conaffinity=0)
                arena.mjcf_model.worldbody.add("geom",name="pointer_target",type="sphere",pos=[0,0,-10],
                                             size=[.008],rgba=[.2,.9,1,1],contype=0,conaffinity=0,group=2)
                for name,kind,size in SLOTS:
                    placed=arena.mjcf_model.worldbody.add(
                        "body",name=name+"_body",mocap=True,pos=[0,0,-10],
                    )
                    placed.add(
                        "geom",name=name,type=kind,size=[size*.1]*(3 if kind=="box" else 1),
                        rgba=[.3,.55,.8,1] if kind=="box" else [.65,.3,.6,1],
                        contype=1,conaffinity=1,
                    )
            super().__init__(
                walker=FruitFly, arena=arena, time_limit=seconds + 0.01,
                disable_wings=False, joint_filter=0.01, future_steps=64,
                body_pitch_angle=47.5,
            )
            self.walkers=[self.walker]
            for index in range(1,fly_count):
                extra=FruitFly(name=f"walker_{index}",use_legs=True,use_wings=True,
                               use_mouth=False,use_antennae=False,joint_filter=.01,
                               physics_timestep=.00005,control_timestep=CONTROL_DT,
                               body_pitch_angle=47.5)
                extra.create_root_joints(arena.attach(extra))
                for sensor in extra.observables.vestibular+extra.observables.proprioception:
                    sensor.enabled=True
                for sensor in (extra.observables.appendages_pos,extra.observables.force,extra.observables.touch):
                    sensor.enabled=True
                extra.observables.self_contact.enabled=False
                for part in extra.mjcf_model.find_all("body"):
                    if any(name in part.name for name in ("coxa","femur","tibia","tarsus","claw")):
                        for wing in ("wing_left","wing_right"):
                            extra.mjcf_model.contact.add("exclude",name=f"{part.name}_{wing}",
                                                        body1=part.name,body2=wing)
                self.walkers.append(extra)
            self.set_timesteps(physics_timestep=0.00005, control_timestep=CONTROL_DT)
            for axis, gain in zip(["yaw", "roll", "pitch"], _WING_PARAMS["gainprm"]):
                self.walker.mjcf_model.find("default", axis).general.gainprm[0] = gain
            for joint in self._wing_joints:
                actuator = self.walker.mjcf_model.find("actuator", joint.name)
                actuator.dyntype = "none"
                actuator.dynprm = (1,)
            wing_default = self.walker.mjcf_model.find("default", "wing").joint
            wing_default.stiffness = _WING_PARAMS["stiffness"]
            wing_default.damping = _WING_PARAMS["damping"]
            for geom in self.walker.mjcf_model.find_all("geom"):
                if "fluid" in geom.name:
                    geom.fluidshape = "ellipsoid"
                    geom.fluidcoef = _WING_PARAMS["fluidcoef"]
            for extra in self.walkers[1:]:
                for axis,gain in zip(("yaw","roll","pitch"),_WING_PARAMS["gainprm"]):
                    extra.mjcf_model.find("default",axis).general.gainprm[0]=gain
                extra.mjcf_model.find("default","wing").joint.stiffness=_WING_PARAMS["stiffness"]
                extra.mjcf_model.find("default","wing").joint.damping=_WING_PARAMS["damping"]
                for joint in extra.mjcf_model.find_all("joint"):
                    if any(axis in joint.name for axis in ("yaw","roll","pitch")):
                        actuator=extra.mjcf_model.find("actuator",joint.name)
                        actuator.dyntype="none";actuator.dynprm=(1,)
                for geom in extra.mjcf_model.find_all("geom"):
                    if "fluid" in geom.name:
                        geom.fluidshape="ellipsoid";geom.fluidcoef=_WING_PARAMS["fluidcoef"]

        def action_spec(self,physics):
            if fly_count==1:
                return super().action_spec(physics)
            from fly_multibody import actor_specifications
            from dm_env import specs
            specifications=actor_specifications(self.walkers,physics)
            return specs.BoundedArray((sum(spec.shape[0] for spec,_ in specifications),),float,
                np.concatenate([spec.minimum for spec,_ in specifications]),
                np.concatenate([spec.maximum for spec,_ in specifications]),
                name="\t".join(f"{walker.name}/{name}" for walker,(spec,_) in zip(self.walkers,specifications)
                               for name in spec.name.split("\t")))

        def before_step(self,physics,action,random_state):
            if fly_count==1:
                return super().before_step(physics,action,random_state)
            from fly_multibody import apply_actor_actions
            self._step_counter+=1
            apply_actor_actions(self.walkers,physics,action,self.actor_control_specs)

        def initialize_episode(self, physics, random_state):
            super().initialize_episode(physics, random_state)
            if fly_count>1:
                from fly_multibody import actor_specifications
                self.actor_control_specs=actor_specifications(self.walkers,physics)
            if not airborne and initial_position is not None:
                if len(initial_position)!=3 or any(not math.isfinite(v) for v in initial_position):
                    raise ValueError("Diagnostic initial position must be a finite vector")
                self.walker.set_pose(physics,initial_position,
                                     [math.cos(initial_heading/2),0,0,math.sin(initial_heading/2)])
            physics.bind(self._wing_joints).qpos = self._wing_springrefs
            from fly_multibody import spawn_layout
            separated=spawn_layout(habitat,fly_count) if fly_count>1 else None
            for index,extra in enumerate(self.walkers[1:],1):
                position,yaw=separated[index]
                extra.set_pose(physics,position,[math.cos(yaw/2),0,0,math.sin(yaw/2)])
                joints=[joint for joint in extra.mjcf_model.find_all("joint")
                        if any(axis in joint.name for axis in ("yaw","roll","pitch"))]
                physics.bind(joints).qpos=[float(j.springref or j.dclass.joint.springref or 0) for j in joints]
            self.launch_time = None
            self.launch_origin = None
            self.landing_time = None
            self.landing_origin = None
            self.walk_origin = np.zeros(3)
            self.walk_start = 0.0
            if wing_pattern is not None:
                from flybody.tasks.pattern_generators import WingBeatPatternGenerator
                self.wbpg = WingBeatPatternGenerator(base_pattern_path=str(wing_pattern))
                if airborne:
                    angles, velocities = self.wbpg.reset(initial_phase=initial_wing_phase, return_qvel=True)
                else:
                    self.wbpg.reset(initial_phase=0.5)
            if airborne:
                if wing_pattern is None:
                    raise ValueError("Airborne diagnostic requires verified wing patterns")
                from flybody.quaternions import mult_quat
                quat = mult_quat(np.array([math.cos(initial_heading/2),0,0,math.sin(initial_heading/2)]),
                                 np.array([math.cos(math.radians(47.5)/2),0,-math.sin(math.radians(47.5)/2),0]))
                self.walker.set_pose(physics, [0, 0, 1], quat)
                self.walker.set_velocity(physics, [20*math.cos(initial_heading),20*math.sin(initial_heading),0])
                physics.bind(self._wing_joints).qpos = angles
                physics.bind(self._wing_joints).qvel = velocities

        def begin_launch(self, physics):
            self.launch_time = physics.time()
            position, _ = self.walker.get_pose(physics)
            self.launch_origin = position.copy()
            # Reset only the controller's phase, never physical joint state.
            self.wbpg.reset(initial_phase=0.5)

        def begin_landing(self, physics):
            self.landing_time = physics.time()
            position, _ = self.walker.get_pose(physics)
            self.landing_origin = position.copy()

        def get_reward_factors(self, physics):
            return (1,)

    return composer.Environment(
        task=UnifiedTask(), time_limit=seconds + 0.01,
        random_state=np.random.RandomState(0), strip_singleton_obs_buffer_dim=True,
    )


class MotorAdapter:
    def __init__(self, env):
        import numpy as np
        from flybody.fruitfly.fruitfly import FruitFly
        from dm_env import specs

        self.np = np
        self.env = env
        self.shared = env.task.walker
        self.spec = env.action_spec()
        shared_joints = [j.name for j in self.shared.observable_joints]
        shared_actions = self.spec.name.split("\t")
        self.projections = {}
        for family in ["walking", "flight"]:
            template = FruitFly(
                use_legs=family == "walking", use_wings=family == "flight",
                joint_filter=0.01 if family == "walking" else 0,
                physics_timestep=0.00005, control_timestep=CONTROL_DT,
                num_user_actions=1 if family == "flight" else 0,
            )
            actions = []
            for group in template._action_indices:
                if group == "user":
                    actions.extend(["user_0"] if family == "flight" else [])
                elif template._ctrl_indices[group]:
                    actuators = template.mjcf_model.find_all("actuator")
                    actions.extend(actuators[i].name for i in template._ctrl_indices[group])
            physical = [name for name in actions if name != "user_0"]
            indices = named_indices(shared_actions, physical)
            low = self.spec.minimum[indices].tolist()
            high = self.spec.maximum[indices].tolist()
            if family == "flight":
                low.append(-1); high.append(1)
            self.projections[family] = {
                "joint_indices": named_indices(shared_joints, [j.name for j in template.observable_joints]),
                "action_indices": indices,
                "spec": specs.BoundedArray(
                    shape=(len(actions),), dtype=float, minimum=np.array(low), maximum=np.array(high),
                    name="\t".join(actions),
                ),
            }
        self.wing_indices = named_indices(shared_actions, [j.name for j in env.task._wing_joints])
        self.wing_joints = env.task._wing_joints
        self.leg_indices = named_indices(shared_actions, [
            name for name in shared_actions if any(part in name for part in ["T1", "T2", "T3"]) and "adhere" not in name
        ])
        self.leg_targets = []
        for index in self.leg_indices:
            joint = self.shared.mjcf_model.find("joint", shared_actions[index])
            if joint is None:
                # Coupled tendon channels use their existing neutral control.
                self.leg_targets.append(float((self.spec.minimum[index] + self.spec.maximum[index]) / 2))
            else:
                self.leg_targets.append(float(joint.springref or joint.dclass.joint.springref or 0))

    def walking_observation(self, observation, speed_cm_s, navigation=None):
        import numpy as np
        from flybody.quaternions import get_dquat_local

        position, quat = self.shared.get_pose(self.env.physics)
        horizon = np.arange(65) * 0.002
        origin = self.env.task.walk_origin
        target = np.column_stack((origin[0]+speed_cm_s * (self.env.physics.time()-self.env.task.walk_start + horizon),
                                  np.full(65,origin[1]), np.full(65, 0.1278)))
        result = dict(observation)
        target_quats = np.tile([1.,0,0,0],(65,1))
        if navigation is not None:
            samples = [navigation.reference(self.env.physics.time()+float(t)) for t in horizon]
            target = np.array([sample[0] for sample in samples])
            target_quats = np.array([[math.cos(sample[2]/2),0,0,math.sin(sample[2]/2)] for sample in samples])
        result["walker/ref_displacement"] = self.shared.transform_vec_to_egocentric_frame(
            self.env.physics, target - position,
        )
        result["walker/ref_root_quat"] = get_dquat_local(quat, target_quats)
        indices = self.projections["walking"]["joint_indices"]
        for key in ["walker/joints_pos", "walker/joints_vel"]:
            result[key] = observation[key][indices]
        result.pop("walker/thorax_height", None)
        return result

    def walking_action(self, action):
        result = self.np.zeros(self.spec.shape)
        result[self.projections["walking"]["action_indices"]] = action
        # Wing position is held by actuator torque, not a body/joint reset.
        current = self.env.physics.bind(self.wing_joints).qpos
        result[self.wing_indices] = self.env.task._wing_springrefs - current
        return self.np.clip(result, self.spec.minimum, self.spec.maximum)

    def flight_observation(self, observation, speed_cm_s=20, navigation=None):
        from flybody.quaternions import get_dquat_local
        np = self.np
        position, quat = self.shared.get_pose(self.env.physics)
        horizon = np.arange(6) * CONTROL_DT
        launch_time = self.env.task.launch_time or 0
        origin = self.env.task.launch_origin if self.env.task.launch_origin is not None else np.zeros(3)
        target = np.column_stack((origin[0] + speed_cm_s * (self.env.physics.time() - launch_time + horizon),
                                  np.full(6, origin[1]), np.ones(6)))
        target_quat = [math.cos(math.radians(47.5)/2), 0, -math.sin(math.radians(47.5)/2), 0]
        if self.env.task.landing_time is not None:
            elapsed = np.clip(self.env.physics.time()-self.env.task.landing_time+horizon,0,0.8)
            origin = self.env.task.landing_origin
            target[:,0] = origin[0]+20*(elapsed-elapsed**2/(2*0.8))
            target[:,1] = origin[1]
            target[:,2] = np.maximum(0.1278, origin[2]-(origin[2]-0.1278)*elapsed/0.8)
        target_quats = np.tile(target_quat, (6, 1))
        if navigation is not None:
            from flybody.quaternions import mult_quat
            samples = [navigation.reference(self.env.physics.time()+time) for time in horizon]
            target = np.array([sample[0] for sample in samples])
            target_quats = np.array([
                mult_quat(np.array([math.cos(sample[2]/2),0,0,math.sin(sample[2]/2)]),np.array(target_quat))
                for sample in samples
            ])
        result = {key: observation[key] for key in [
            "walker/gyro", "walker/accelerometer", "walker/velocimeter", "walker/world_zaxis",
        ]}
        result["walker/ref_displacement"] = self.shared.transform_vec_to_egocentric_frame(self.env.physics, target-position)
        result["walker/ref_root_quat"] = get_dquat_local(quat, target_quats)
        for key in ["walker/joints_pos", "walker/joints_vel"]:
            result[key] = observation[key][self.projections["flight"]["joint_indices"]]
        # The published flight policy has no activation channels; filtered leg
        # channels remain physical but are not part of its trained observation.
        result["walker/actuator_activation"] = np.empty(0)
        return result

    def flight_target(self):
        np = self.np
        if self.env.task.landing_time is not None:
            elapsed = np.clip(self.env.physics.time()-self.env.task.landing_time, 0, 0.8)
            origin = self.env.task.landing_origin
            return np.array([
                origin[0]+20*(elapsed-elapsed**2/(2*0.8)), origin[1],
                max(0.1278, origin[2]-(origin[2]-0.1278)*elapsed/0.8),
            ])
        origin = self.env.task.launch_origin if self.env.task.launch_origin is not None else np.zeros(3)
        return np.array([origin[0]+20*(self.env.physics.time()-(self.env.task.launch_time or 0)),origin[1],1])

    def flight_action(self, action):
        result = self.np.zeros(self.spec.shape)
        result[self.projections["flight"]["action_indices"]] = action[:-1]
        result[self.leg_indices] = self.leg_targets
        frequency = self.env.task.wbpg.base_beat_freq * (1 + self.env.task.wbpg.rel_freq_range * action[-1])
        angles = self.env.task.wbpg.step(ctrl_freq=frequency)
        current = self.env.physics.bind(self.wing_joints).qpos
        result[self.wing_indices] += angles - current
        return self.np.clip(result, self.spec.minimum, self.spec.maximum)

    def leg_extension_action(self, action, activation):
        from fly_leg_extension import TIBIA_EXTENSION_RAD

        if not math.isfinite(activation) or not 0 <= activation <= 1:
            raise ValueError("Leg activation must be finite and in [0, 1]")
        result = action.copy()
        names = self.spec.name.split("\t")
        required = [f"tibia_T{leg}_{side}" for leg in (1, 2, 3) for side in ("left", "right")]
        indices = named_indices(names, required)
        if activation:
            result[indices] += activation * TIBIA_EXTENSION_RAD
        return self.np.clip(result, self.spec.minimum, self.spec.maximum)


def run(data_dir, output, seconds=1.0, speed_cm_s=2.0, airborne=False, takeoff_test=False,
        arena_half_size_mm=30, landing_test=False, view=False, scene=None):
    import numpy as np

    if not math.isfinite(seconds) or not 0.1 <= seconds <= 10:
        raise ValueError("Unified walking diagnostic duration must be in [0.1, 10] seconds")
    if not math.isfinite(speed_cm_s) or not 0 <= speed_cm_s <= 4:
        raise ValueError("Walking reference speed must be in [0, 4] cm/s")
    if airborne and takeoff_test:
        raise ValueError("Airborne initialization and grounded takeoff tests are distinct")
    if takeoff_test and seconds < 1.5:
        raise ValueError("Grounded takeoff test requires at least 1.5 simulated seconds")
    if not math.isfinite(arena_half_size_mm) or arena_half_size_mm<30:
        raise ValueError("Arena half-size must be finite and at least 30 mm")
    if landing_test and (not takeoff_test or seconds<2.5):
        raise ValueError("Landing test requires --takeoff-test and at least 2.5 seconds")
    output = output.expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()
    if data_dir == ROOT or ROOT in data_dir.parents:
        raise ValueError("Unified simulation inputs must be outside Git")
    if output == ROOT or ROOT in output.parents or output.exists():
        raise ValueError("Choose a new external unified output directory")
    habitat = Environment.load(scene if scene is not None else ROOT / "experiments/fly-walking/habitat.json")
    habitat = replace(habitat,half_size_mm=arena_half_size_mm)
    paths = prepare_data(data_dir) if airborne or takeoff_test else None
    env = create_environment(habitat, seconds, airborne, paths["wing_pattern_fmech.npy"] if paths else None)
    output.mkdir(parents=True)
    (output / "status.json").write_text('{"status":"running"}\n')
    (output / "environment.json").write_text(json.dumps(environment_dict(habitat), indent=2) + "\n")
    records = []
    brain = None
    trigger_time = None
    initial_contact = False
    flight_contacts = 0
    flight_steps = 0
    boundary_steps = 0
    transition = None
    landing_contact_steps = 0
    landed_at = None
    brain_responses = []
    landed_step = None
    handoffs = []
    viewer = None
    observer = None
    commands = queue.SimpleQueue()
    paused = False
    close_requested = False
    completed_steps = 0
    started = time.perf_counter()
    resources = ExitStack()
    if takeoff_test:
        simulation_steps(seconds, 0.01)
    try:
        timestep = env.reset()
        adapter = MotorAdapter(env)
        family = "flight" if airborne else "walking"
        policy = PublishedMotorPolicy(prepare_policy(data_dir, CATALOG, family))
        flight_policy = PublishedMotorPolicy(prepare_policy(data_dir, CATALOG, "flight")) if takeoff_test else policy
        if takeoff_test:
            brain = BrainClient(ROOT / ".venv/bin/python", data_dir, output, 420, takeoff=True)
            (output / "brain-metadata.json").write_text(json.dumps(brain.metadata, indent=2) + "\n")
        before_mass = env.physics.model.body_mass.copy()
        before_inertia = env.physics.model.body_inertia.copy()
        body = env.physics.model.name2id("walker/thorax", "body")
        ground = env.physics.model.name2id("groundplane", "geom")
        from fly_flight_arena import FlyContactReader
        contact_reader = FlyContactReader(env.physics.model.ptr, habitat)
        mass = float(sum(env.physics.model.body_mass[i] for i in range(env.physics.model.nbody)
                         if (env.physics.model.id2name(i, "body") or "").startswith("walker")))
        initial, _ = env.task.walker.get_pose(env.physics)
        initial = initial.copy()
        action = np.zeros(env.action_spec().shape)
        guard = None
        if view:
            import mujoco as mj
            observer = ObserverScene(env.physics.model.ptr, env.physics.data.ptr)
            guard = ViewerStateGuard(env.physics.model.ptr, env.physics.data.ptr)
            viewer = resources.enter_context(managed_viewer(
                observer.model, observer.data, key_callback=commands.put,
                show_left_ui=False, show_right_ui=False,
            ))
            viewer.cam.type = mj.mjtCamera.mjCAMERA_FREE
            viewer.cam.lookat[:] = initial
            viewer.cam.distance = 1.0
            viewer.cam.azimuth = 135
            viewer.cam.elevation = -25
        for step in range(simulation_steps(seconds, CONTROL_DT)):
            if viewer is not None and step % 50 == 0:
                while True:
                    while not commands.empty():
                        code = commands.get()
                        if code in {ord("P"), 32}:
                            paused = not paused
                        elif code == ord("Q"):
                            close_requested = True
                        elif code == ord("C"):
                            viewer.cam.type = (
                                mj.mjtCamera.mjCAMERA_FREE if viewer.cam.type == mj.mjtCamera.mjCAMERA_TRACKING
                                else mj.mjtCamera.mjCAMERA_TRACKING
                            )
                            viewer.cam.trackbodyid = body
                    if not viewer.is_running():
                        close_requested = True
                    if close_requested:
                        break
                    with viewer.lock():
                        guard.restore_if_changed()
                        observer.sync()
                        scene = viewer.user_scn
                        scene.ngeom = 1
                        mj.mjv_initGeom(scene.geoms[0],mj.mjtGeom.mjGEOM_LABEL,np.zeros(3),
                                        env.physics.data.xpos[body],np.eye(3).ravel(),np.ones(4))
                        scene.geoms[0].label = "HYBRID single body: P pause / C camera / Q save"
                    viewer.sync()
                    if not paused:
                        break
                    time.sleep(0.02)
                if close_requested:
                    break
            if brain is not None and step % 50 == 0:
                # Explicit diagnostic upstream stimulation, not a fitted retinal
                # encoder or automatic timer that directly launches the body.
                brain.begin_step(10, False, 0.3 <= env.physics.time() < 0.4)
                neural_response = brain.finish_step()
                brain_responses.append(neural_response)
            elapsed = None if trigger_time is None else env.physics.time() - trigger_time
            phase = "flight" if airborne else (
                "walking" if elapsed is None else "assisted-launch" if elapsed < 0.3 else "flight"
            )
            if landing_test and elapsed is not None and elapsed>=0.9 and env.task.landing_time is None:
                before_qpos, before_qvel = env.physics.data.qpos.copy(), env.physics.data.qvel.copy()
                env.task.begin_landing(env.physics)
                handoffs.append({
                    "phase":"landing", "time_s":env.physics.time(),
                    "qpos_preserved":bool(np.array_equal(before_qpos,env.physics.data.qpos)),
                    "qvel_preserved":bool(np.array_equal(before_qvel,env.physics.data.qvel)),
                })
            if env.task.landing_time is not None:
                phase = "landing" if landed_at is None else "post-landing-walk"
            env.physics.data.xfrc_applied[body] = 0
            if (airborne or trigger_time is not None) and landed_at is None:
                observation = adapter.flight_observation(timestep.observation)
                motor, _ = flight_policy.action(observation, adapter.projections["flight"]["spec"])
                action = adapter.flight_action(motor)
                if phase == "assisted-launch":
                    import mujoco as mj
                    velocity = np.zeros(6)
                    mj.mj_objectVelocity(env.physics.model.ptr, env.physics.data.ptr, mj.mjtObj.mjOBJ_BODY, body, velocity, False)
                    desired_quat = np.array([math.cos(math.radians(47.5)/2), 0, -math.sin(math.radians(47.5)/2), 0])
                    desired_rotation = np.zeros(9)
                    mj.mju_quat2Mat(desired_rotation, desired_quat)
                    origin = env.task.launch_origin
                    target = np.array([origin[0] + 20 * elapsed, origin[1], 1])
                    env.physics.data.xfrc_applied[body] = assisted_force(
                        mass, env.physics.data.xpos[body], velocity,
                        env.physics.data.xmat[body].reshape(3, 3), desired_rotation.reshape(3, 3), target,
                    )
            elif step % WALK_EVERY == 0 or (phase == "post-landing-walk" and step == landed_step):
                observation = adapter.walking_observation(timestep.observation, speed_cm_s)
                motor, _ = policy.action(observation, adapter.projections["walking"]["spec"])
                action = adapter.walking_action(motor)
            else:
                # Recompute wing holding torques against current joint state.
                action = adapter.walking_action(motor)
            timestep = env.step(action.copy())
            completed_steps += 1
            if guard is not None:
                guard.capture()
            floor_contacts = contact_reader.sample(env.physics.data.ptr)
            if phase == "walking":
                initial_contact |= floor_contacts > 0
            if phase == "flight":
                flight_steps += 1
                flight_contacts += int(floor_contacts > 0)
            if phase=="landing":
                landing_contact_steps = landing_contact_steps+1 if floor_contacts>0 else 0
                if landing_contact_steps>=250 and env.physics.bind(env.task.walker.root_body).xmat.reshape(3,3)[2,2]>0.8:
                    landed_at=env.physics.time()
                    landed_step=step+1
                    env.task.walk_origin=env.task.walker.get_pose(env.physics)[0].copy()
                    env.task.walk_start=landed_at
                    handoffs.append({"phase":"post-landing-walk","time_s":landed_at,
                                     "qpos_preserved":True,"qvel_preserved":True})
            position, quat = env.task.walker.get_pose(env.physics)
            if not np.isfinite(env.physics.data.qpos).all() or not np.isfinite(env.physics.data.qvel).all():
                raise RuntimeError("Unified physical state became nonfinite")
            if step % WALK_EVERY == 0:
                expected = [speed_cm_s * env.physics.time(), 0, 0.1278]
                if phase == "post-landing-walk":
                    origin=env.task.walk_origin
                    expected=[origin[0]+speed_cm_s*(env.physics.time()-landed_at),origin[1],0.1278]
                elif airborne or trigger_time is not None:
                    expected = adapter.flight_target()
                records.append({
                    "time_s": env.physics.time(), "position_cm": position.tolist(),
                    "quaternion": quat.tolist(), "contacts": env.physics.data.ncon,
                    "position_error_cm": float(np.linalg.norm(position - expected)),
                    "phase": phase, "floor_contacts": floor_contacts,
                    "external_force_torque": env.physics.data.xfrc_applied[body].tolist(),
                })
            boundary_steps += int(any(abs(value*10) > habitat.half_size_mm for value in position[:2]))
            if brain is not None and (step+1) % 50 == 0:
                if abs(neural_response["brain_time_ms"] - env.physics.time()*1000) > 1e-6:
                    raise RuntimeError("Unified body and brain interval clocks diverged")
                if trigger_time is None and sum(neural_response["giant_fiber_spikes"].values()) > 0:
                    before_qpos, before_qvel = env.physics.data.qpos.copy(), env.physics.data.qvel.copy()
                    env.task.begin_launch(env.physics)
                    trigger_time = env.physics.time()
                    transition = {
                        "time_s": trigger_time, "qpos_preserved": bool(np.array_equal(before_qpos, env.physics.data.qpos)),
                        "qvel_preserved": bool(np.array_equal(before_qvel, env.physics.data.qvel)),
                    }
                    if not transition["qpos_preserved"] or not transition["qvel_preserved"]:
                        raise RuntimeError("Motor handoff changed physical integration state")
            if timestep.last():
                raise RuntimeError("Unified walking terminated before the requested diagnostic duration")
        final, quat = env.task.walker.get_pose(env.physics)
        upright = float(env.physics.bind(env.task.walker.root_body).xmat.reshape(3, 3)[2, 2])
        unchanged = (
            np.array_equal(before_mass, env.physics.model.body_mass)
            and np.array_equal(before_inertia, env.physics.model.body_inertia)
        )
        passed, thresholds = evaluate_motor(
            records, initial, final, upright, seconds, 20 if airborne else speed_cm_s,
            airborne, takeoff_test, landing_test, trigger_time, initial_contact,
            flight_steps, flight_contacts, boundary_steps, landed_at, unchanged,
        )
        passed = passed and completed_steps == simulation_steps(seconds, CONTROL_DT)
        summary = {
            "status": "closed_by_user" if close_requested else "completed",
            "motor_check_passed": bool(passed), "family": family, "requested_seconds": seconds,
            "seconds":completed_steps*CONTROL_DT,"wall_seconds":time.perf_counter()-started,
            "speed_cm_s": 20 if airborne else speed_cm_s, "final_position_cm": final.tolist(), "upright_cosine": upright,
            "takeoff_test": takeoff_test, "neural_trigger_time_s": trigger_time, "handoff": transition,
            "initial_floor_contact": initial_contact, "flight_steps": flight_steps, "flight_contact_steps": flight_contacts,
            "arena_exit_steps": boundary_steps,
            "landing_test":landing_test,"landed_at_s":landed_at,
            "controller_transitions":handoffs,"arena_half_size_mm":arena_half_size_mm,
            "initial_position_cm": initial.tolist(), "legs_and_wings_on_same_body": True,
            "runtime_pose_resets": 0, "learned_motor_controller": True, "neural_motor_decoding": False,
            "maximum_position_error_cm": max((r["position_error_cm"] for r in records),default=None),
            "thresholds": thresholds,
            "body_mass_sha256": hashlib.sha256(before_mass.tobytes()).hexdigest(),
            "body_inertia_sha256":hashlib.sha256(before_inertia.tobytes()).hexdigest(),
            "model_mass_inertia_unchanged":bool(unchanged),
            "source_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_model_revision":"d015e9bfe441bd90ae431bac24c55cb74bdbce26",
            "native_viewer":view,"viewer_state_edit_rejections":guard.rejections if guard else 0,
            "limitations": ["Landing is not yet validated on this body.", "Policies use privileged synthetic references.", "Shared actuator filters and faster sensor cadence differ from walking training.", "Takeoff test uses explicit upstream Poisson stimulation and external force assistance.", "Original 30mm-half-size habitat may be exited; exits are logged, not hidden."],
        }
        (output / "trajectory.json").write_text(json.dumps(records) + "\n")
        if brain_responses:
            (output/"brain-intervals.json").write_text(json.dumps(brain_responses)+"\n")
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "status.json").write_text(json.dumps({"status":summary["status"]})+"\n")
        print(json.dumps(summary, indent=2))
        if viewer is not None and not close_requested:
            (output/"status.json").write_text('{"status":"awaiting_viewer_close"}\n')
            while viewer.is_running():
                while not commands.empty():
                    if commands.get()==ord("Q"):
                        close_requested=True
                if close_requested:
                    break
                with viewer.lock():
                    observer.sync()
                    viewer.user_scn.geoms[0].label=(
                        "DONE: Q saves/closes" if passed else "FAILED CHECK: inspect / Q closes"
                    )
                viewer.sync()
                time.sleep(0.02)
            (output/"status.json").write_text(json.dumps({"status":summary["status"]})+"\n")
        return passed or close_requested
    except Exception as error:
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": str(error)}) + "\n")
        raise
    finally:
        try:
            resources.close()
        finally:
            try:
                if brain is not None:
                    brain.close()
            finally:
                env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--speed-cm-s", type=float, default=2)
    parser.add_argument("--airborne-diagnostic", action="store_true", help="Explicit initial airborne flight-policy test; not a takeoff")
    parser.add_argument("--takeoff-test", action="store_true", help="Explicit upstream neural stimulus after walking; GF initiates assisted launch")
    parser.add_argument("--arena-half-size-mm",type=float,default=30,help="Explicit arena size; fast flight needs more room")
    parser.add_argument("--landing-test",action="store_true",help="Experimental synthetic descent after flight; not biological landing")
    parser.add_argument("--view",action="store_true",help="Display the same physical body with observer graphics; P pause, C tracking, Q save")
    parser.add_argument("--scene",type=Path,help="Shared habitat JSON including optional version-2 plants/materials")
    args = parser.parse_args()
    try:
        passed = run(args.data_dir, args.output_dir, args.seconds, args.speed_cm_s, args.airborne_diagnostic, args.takeoff_test,
                     args.arena_half_size_mm,args.landing_test,args.view,args.scene)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print(f"ERROR: unified diagnostic failed: {error}", file=sys.stderr)
        return 1
    if not passed:
        print("ERROR: unified motor acceptance check failed; inspect saved result", file=sys.stderr)
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
