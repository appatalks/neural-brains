"""Interactive NeuroMechFly walking sandbox, not a connectome-driven controller."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import queue
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from fly_environment import (
    Environment, MotorCommand, Terrain, environment_dict, load_schedule,
    sample_environment, sensory_command,
    object_definitions,
)
from sim_units import WALKING_UNITS, simulation_steps
from sim_viewer import managed_viewer, ViewerStateGuard
from fly_recovery import Recovery, recovery_offsets
from fly_feeding import BrainClient, FeedingConfig, feeding_hashes
from fly_graphics import ObserverScene
from fly_finger import Pointer, pointer_target
from fly_looming import SphereLooming, finger_visibility
from fly_objects import Objects, SLOTS
from fly_dashboard import DEFAULT_PORT
from fly_performance import PhaseTimings
from fly_gait_observation import GaitObservationReader
from fly_world_renderer import BrowserInputs, WorldRenderer


ROOT = Path(__file__).resolve().parents[1]
REVISION = "38c8ec61034cd59bc5ba0de20688d4a3c0000d60"
CODE_HASHES = {
    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "environment_module_sha256": hashlib.sha256((ROOT / "scripts/fly_environment.py").read_bytes()).hexdigest(),
    "unit_module_sha256": hashlib.sha256((ROOT / "scripts/sim_units.py").read_bytes()).hexdigest(),
    "recovery_module_sha256": hashlib.sha256((ROOT / "scripts/fly_recovery.py").read_bytes()).hexdigest(),
    "looming_module_sha256": hashlib.sha256((ROOT / "scripts/fly_looming.py").read_bytes()).hexdigest(),
    "gait_observation_module_sha256": hashlib.sha256((ROOT / "scripts/fly_gait_observation.py").read_bytes()).hexdigest(),
    "world_renderer_module_sha256": hashlib.sha256((ROOT / "scripts/fly_world_renderer.py").read_bytes()).hexdigest(),
}


@dataclass
class Controls:
    drive: float = 1.0
    turn: float = 0.0
    paused: bool = False
    obstacles: bool = True
    slippery: bool = False
    playback: float = 1.0
    sensory: bool = False
    follow_camera: bool = False
    sugar_enabled: bool = True
    autonomous: bool = False
    finger_enabled: bool = False

    def __post_init__(self):
        if self.autonomous:
            self.sensory = True
            self.turn = 0.0

    def motor_command(self) -> MotorCommand:
        return MotorCommand(*self.signal())

    def key(self, code: int) -> str | None:
        key = chr(code).upper() if 0 <= code < 256 else ""
        if self.autonomous and key in {"W", "S", "A", "D", "X", "N"}:
            return None
        if key == "W":
            self.drive = min(1.5, self.drive + 0.1)
        elif key == "S":
            self.drive = max(0.0, self.drive - 0.1)
        elif key == "A":
            self.turn = max(-0.8, self.turn - 0.1)
        elif key == "D":
            self.turn = min(0.8, self.turn + 0.1)
        elif key == "X":
            self.turn = 0.0
        elif key == "P":
            self.paused = not self.paused
        elif key == "O":
            self.obstacles = not self.obstacles
        elif key == "F":
            self.slippery = not self.slippery
        elif key == "N":
            self.sensory = not self.sensory
        elif key == "C":
            self.follow_camera = not self.follow_camera
        elif key == "T":
            self.sugar_enabled = not self.sugar_enabled
        elif key == "H":
            self.finger_enabled = not self.finger_enabled
        elif key == "[":
            self.playback = max(0.1, self.playback / 2)
        elif key == "]":
            self.playback = min(2.0, self.playback * 2)
        elif key not in {"R", "B", "Q", "1", "2", "3"}:
            return None
        return key

    def signal(self) -> tuple[float, float]:
        return (
            max(0.0, min(1.5, self.drive + self.turn)),
            max(0.0, min(1.5, self.drive - self.turn)),
        )


def control_help(autonomous: bool) -> str:
    if autonomous:
        return (
            "Autonomous hybrid habitat - environment interaction only\n"
            "T sugar | O terrain | F friction | B external push\n"
            "H virtual finger (pointer follows arena plane)\n"
            "1 place cube | 2 place sphere | 3 remove last object\n"
            "P pause | R restart experiment | C camera follow | Q save/close\n"
            "[/] playback | mouse pan/orbit/zoom\n"
            "Feeding: actual FlyWire spikes; movement/recovery: engineered"
        )
    return (
        "Locomotion baseline; feeding circuit separate\n"
        "W/S drive | A/D turn | X straight | P pause\n"
        "O obstacles | F slippery | B lateral push | R reset\n"
        "N sensory-demo controller (NOT brain)\n"
        "T toggle sugar exposure (live feeding bridge only)\n"
        "C toggle camera follow (free pan by default)\n"
        "Q save and close\n"
        "[/] playback | mouse orbit/zoom; B applies logged force"
    )


def external_output(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError("Output directory must be outside the repository")
    if path.exists():
        raise FileExistsError("Choose a new output directory; existing runs are not overwritten")
    return path


def eye_inset_bounds(left: int, bottom: int, width: int, height: int) -> tuple[int, int, int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Viewer viewport must have positive dimensions")
    margin = min(10, (min(width, height) - 1) // 2)
    image_width = min(320, width - 2 * margin)
    image_height = min(160, height - 2 * margin)
    return (
        left + width - image_width - margin,
        bottom + height - image_height - margin, image_width, image_height,
    )


def build_scene(
    environment: Environment | None = None, vision: bool = False,
    feeding: FeedingConfig | None = None, virtual_finger: bool = False,
):
    if environment is not None and environment.schema_version >= 3:
        raise ValueError("Movable grassland habitat requires the unified FlyBody backend; FlyGym version-1/2 scenes remain supported")
    import mujoco as mj
    import numpy as np
    from flygym import Simulation
    from flygym.anatomy import BodySegment, ContactBodiesPreset
    from flygym.compose import FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import (
        HybridTurningController, LocomotionAction, PreprogrammedSteps,
        apply_locomotion_action, make_locomotion_fly,
    )

    fly = make_locomotion_fly(name="walking_fly", add_adhesion=True, colorize=True)
    if vision:
        fly.add_vision()
    habitat = environment is not None
    if environment is None:
        environment = Environment(
            1000, 0, (1.0, 0.005, 0.0001),
            tuple(Terrain(
                f"terrain_bar_{i}", (x, 0, 0.15), (0.2, 3, 0.15), 0,
                (1.0, 0.005, 0.0001),
            ) for i, x in enumerate([5.0, 10.0, 15.0])),
            (), (), (0, 0, 0), 0, 0, 12,
        )
    world = FlatGroundWorld(half_size=environment.half_size_mm)
    world.ground_geom.friction = environment.ground_friction
    for material in environment.materials:
        world.mjcf_root.add_material(
            name=material.name, rgba=material.rgba,
            specular=material.specular, shininess=material.shininess,
        )
    obstacle_geoms = []
    for definition in object_definitions(environment):
        definition["type"] = {
            "box": mj.mjtGeom.mjGEOM_BOX, "ellipsoid": mj.mjtGeom.mjGEOM_ELLIPSOID,
            "sphere": mj.mjtGeom.mjGEOM_SPHERE, "capsule": mj.mjtGeom.mjGEOM_CAPSULE,
        }[definition["type"]]
        definition.update(contype=0, conaffinity=0)
        geom = world.mjcf_root.worldbody.add_geom(**definition)
        world.ground_geoms.append(geom)
    if virtual_finger:
        finger = world.mjcf_root.worldbody.add_body(
            name="virtual_finger", mocap=True, pos=[0, 0, -10],
        )
        finger_geom = finger.add_geom(
            name="virtual_finger_tip", type=mj.mjtGeom.mjGEOM_SPHERE,
            size=[1.5], rgba=[0.85, 0.55, 0.4, 1], contype=0, conaffinity=0,
            friction=[0.8, 0.005, 0.0001],
        )
        world.ground_geoms.append(finger_geom)
        finger.add_geom(
            name="virtual_finger_shaft", type=mj.mjtGeom.mjGEOM_CAPSULE,
            fromto=[0, 0, 0.5, 0, 0, 5], size=[1.1],
            rgba=[0.78, 0.48, 0.34, 1], contype=0, conaffinity=0,
        )
        world.mjcf_root.worldbody.add_geom(
            name="pointer_target", type=mj.mjtGeom.mjGEOM_SPHERE,
            pos=[0, 0, -10], size=[0.08], rgba=[0.2, 0.9, 1, 1],
            contype=0, conaffinity=0, group=2,
        )
        for name, kind, size in SLOTS:
            geom = world.mjcf_root.worldbody.add_geom(
                name=name, type=mj.mjtGeom.mjGEOM_BOX if kind == "box" else mj.mjtGeom.mjGEOM_SPHERE,
                pos=[0, 0, -10], size=[size] * (3 if kind == "box" else 1),
                rgba=[0.3, 0.55, 0.8, 1] if kind == "box" else [0.65, 0.3, 0.6, 1],
                contype=0, conaffinity=0, friction=[1, 0.005, 0.0001],
            )
            world.ground_geoms.append(geom)
    for terrain in environment.terrain:
        geom = world.mjcf_root.worldbody.add_geom(
            name=terrain.name, type=mj.mjtGeom.mjGEOM_BOX,
            size=terrain.half_size_mm, pos=terrain.position_mm,
            quat=[math.cos(terrain.pitch_rad / 2), 0, math.sin(terrain.pitch_rad / 2), 0],
            friction=terrain.friction,
            rgba=[0.8, 0.45, 0.15, 1], contype=0, conaffinity=0,
        )
        world.ground_geoms.append(geom)
        obstacle_geoms.append(geom)
    if environment.walls_height_mm:
        half = environment.half_size_mm
        height = environment.walls_height_mm
        for i, (pos, size) in enumerate([
            ([half, 0, height / 2], [0.25, half, height / 2]),
            ([-half, 0, height / 2], [0.25, half, height / 2]),
            ([0, half, height / 2], [half, 0.25, height / 2]),
            ([0, -half, height / 2], [half, 0.25, height / 2]),
        ]):
            wall = world.mjcf_root.worldbody.add_geom(
                name=f"arena_wall_{i}", type=mj.mjtGeom.mjGEOM_BOX,
                pos=pos, size=size, rgba=[0.3, 0.45, 0.5, 0.35],
                contype=0, conaffinity=0,
            )
            world.ground_geoms.append(wall)
    for source in (*environment.odors, *environment.lights):
        world.mjcf_root.worldbody.add_geom(
            name=source.name, type=mj.mjtGeom.mjGEOM_SPHERE,
            pos=source.position_mm, size=[0.3],
            rgba=[0.1, 0.8, 0.2, 1] if source in environment.odors else [1, 1, 0.2, 1],
            contype=0, conaffinity=0, group=2,
        )
    for i, source in enumerate(environment.lights):
        world.mjcf_root.worldbody.add_light(
            name=f"source_light_{i}", pos=source.position_mm, dir=[0, 0, -1],
            diffuse=[min(source.strength, 1)] * 3,
        )
    if feeding is not None:
        for name in ["sugar_exposure_region", "mn9_readout_marker"]:
            if world.mjcf_root.geom(name) is not None:
                raise ValueError(f"Habitat geometry name conflicts with feeding bridge: {name}")
        world.mjcf_root.worldbody.add_geom(
            name="sugar_exposure_region", type=mj.mjtGeom.mjGEOM_SPHERE,
            pos=feeding.position_mm, size=[feeding.radius_mm],
            rgba=[0.9, 0.2, 0.8, 0.15], contype=0, conaffinity=0, group=2,
        )
        world.mjcf_root.worldbody.add_geom(
            name="mn9_readout_marker", type=mj.mjtGeom.mjGEOM_SPHERE,
            pos=feeding.position_mm, size=[0.12],
            rgba=[0.4, 0.4, 0.4, 1], contype=0, conaffinity=0, group=2,
        )
    world.add_fly(
        fly, [0, 0, 0.8], Rotation3D("quat", [1, 0, 0, 0]),
        bodysegs_with_ground_contact=(
            ContactBodiesPreset.LEGS_THORAX_ABDOMEN_HEAD if habitat
            else ContactBodiesPreset.TIBIA_TARSUS_ONLY
        ),
        add_ground_contact_sensors=False,
    )
    sim = Simulation(world)
    for geom_id in range(sim.mj_model.ngeom):
        name = mj.mj_id2name(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, geom_id) or ""
        if name.startswith(fly.name + "/"):
            sim.mj_model.geom_group[geom_id] = 1
    steps = PreprogrammedSteps()
    dofs = fly.get_actuated_jointdofs_order("position")
    controller = HybridTurningController(
        timestep=sim.timestep, preprogrammed_steps=steps, output_dof_order=dofs
    )

    def reset():
        sim.reset()
        controller.reset(seed=0)
        apply_locomotion_action(sim, fly.name, LocomotionAction(
            joint_angles=steps.default_pose_by_dof_order(dofs),
            adhesion_onoff=np.ones(6, dtype=bool),
        ))
        sim.warmup()

    reset()
    thorax = fly.get_bodysegs_order().index(BodySegment("c_thorax"))
    body_id = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_BODY, fly.name + "/c_thorax")
    obstacle_ids = [
        mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, geom.name)
        for geom in obstacle_geoms
    ]
    ground_id = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, "ground_plane")
    if min([body_id, ground_id, *obstacle_ids]) < 0:
        raise ValueError("Scene body/terrain IDs are missing")
    return sim, fly, controller, reset, thorax, body_id, obstacle_ids, ground_id, environment


def run(
    output: Path, seconds: float, headless: bool,
    scene: Path | None = None, schedule_path: Path | None = None,
    sensory: bool = False, until_closed: bool = False, vision: bool = False,
    self_righting: bool = False, initial_roll_deg: float = 0,
    brain_feeding: Path | None = None, brain_data_dir: Path | None = None,
    brain_python: Path = ROOT / ".venv/bin/python", initial_drive: float = 1.0,
    autonomous: bool = False,
    observer_graphics: bool = False,
    virtual_finger: bool = False,
    objects_path: Path | None = None,
    neural_dashboard: bool = False,
    dashboard_port: int = DEFAULT_PORT,
    browser_app: bool = False,
    cached_gait_observation: bool = True,
):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be a positive finite number of simulated seconds")
    if until_closed and headless and not browser_app:
        raise ValueError("--until-closed requires the interactive viewer")
    if not math.isfinite(initial_roll_deg) or abs(initial_roll_deg) > 180:
        raise ValueError("Initial diagnostic roll must be finite and within +/-180 degrees")
    if not math.isfinite(initial_drive) or not 0 <= initial_drive <= 1.5:
        raise ValueError("Initial locomotion drive must be finite and between 0 and 1.5")
    if (brain_feeding is None) != (brain_data_dir is None):
        raise ValueError("--brain-feeding and --brain-data-dir must be provided together")
    feeding = FeedingConfig.load(brain_feeding) if brain_feeding is not None else None
    if browser_app and not neural_dashboard:
        raise ValueError("Browser app requires the neural dashboard")
    if neural_dashboard and feeding is None:
        raise ValueError("Neuron dashboard requires the actual neural feeding bridge")
    if type(dashboard_port) is not int or not 0 <= dashboard_port <= 65535:
        raise ValueError("Dashboard port must be an integer in [0, 65535]")
    import mujoco as mj
    import numpy as np
    from flygym_demo.complex_terrain import HybridControllerObservation, apply_locomotion_action
    schedule = load_schedule(schedule_path)
    if autonomous and any(entry["key"] in {"W", "S", "A", "D", "X", "N"} for entry in schedule):
        raise ValueError("Autonomous habitat schedules cannot steer the fly or switch controllers")
    if autonomous and feeding is None:
        raise ValueError("The main autonomous habitat requires the actual neural feeding bridge")
    if virtual_finger and feeding is None:
        raise ValueError("Virtual finger/GF integration requires neural feeding worker configuration")
    if virtual_finger and not vision:
        raise ValueError("Virtual finger visual-neuron integration requires --vision for eye-camera visibility")
    if objects_path is not None and not virtual_finger:
        raise ValueError("Saved object placements require --virtual-finger")
    if not until_closed and schedule and schedule[-1]["time_s"] >= seconds:
        raise ValueError("Scheduled events must occur before the requested duration")
    output = external_output(output)
    sim, fly, controller, reset, thorax, body_id, obstacle_ids, ground_id, environment = build_scene(
        Environment.load(scene) if scene is not None else None, vision, feeding, virtual_finger,
    )
    controls = Controls(sensory=sensory, drive=initial_drive, autonomous=autonomous)
    gait_reader = GaitObservationReader(sim, fly.name) if cached_gait_observation else None
    recovery = Recovery()
    dofs = fly.get_actuated_jointdofs_order("position")
    neutral = controller.preprogrammed_steps.default_pose_by_dof_order(dofs)
    offsets = recovery_offsets(dofs) if self_righting else None
    if initial_roll_deg:
        from flygym_demo.complex_terrain import LocomotionAction
        angle = math.radians(initial_roll_deg)
        sim.mj_data.qpos[:7] = [0, 0, 0.8, math.cos(angle / 2), math.sin(angle / 2), 0, 0]
        sim.mj_data.qvel[:] = 0
        apply_locomotion_action(sim, fly.name, LocomotionAction(neutral, np.zeros(6, dtype=bool)))
        mj.mj_forward(sim.mj_model, sim.mj_data)
        sim.warmup(duration_s=0.1)
    target_steps = None if until_closed else simulation_steps(seconds, sim.timestep)
    commands = queue.SimpleQueue()
    original_friction = sim.mj_model.geom_friction[ground_id].copy()
    obstacle_positions = sim.mj_model.geom_pos[obstacle_ids].copy()
    initial = sim.get_body_positions(fly.name)[thorax].copy()
    events = []
    sensor_count = 0
    schedule_index = 0
    episode = 0
    close_requested = False
    latest_observation = sample_environment(sim, fly, body_id, environment, 0, episode)
    latest_motor = controls.motor_command()
    simulated = 0.0
    completed_steps = 0
    bump_until = 0.0
    next_vision_s = 0.0
    eye_frames = None
    eye_time_s = None
    dashboard_vision_samples = 0
    vision_samples = 0
    fallen_observation_frames = 0
    brain_client = None
    dashboard = None
    neural_stream = None
    brain_metadata = None
    brain_records = 0
    brain_mn9_spikes = 0
    brain_network_spikes = 0
    brain_state = None
    exposure = None
    sugar_geom = None
    readout_geom = None
    feeding_provenance = feeding_hashes() if feeding else None
    if neural_dashboard:
        feeding_provenance.update({
            "dashboard_module_sha256": hashlib.sha256((ROOT / "scripts/fly_dashboard.py").read_bytes()).hexdigest(),
            "dashboard_ui_sha256": hashlib.sha256((ROOT / "scripts/dashboard.html").read_bytes()).hexdigest(),
            "connections_module_sha256": hashlib.sha256((ROOT / "scripts/fly_connections.py").read_bytes()).hexdigest(),
            "browser_module_sha256": hashlib.sha256((ROOT / "scripts/fly_browser.py").read_bytes()).hexdigest(),
        })
    looming_state = {"looming_active": False}
    gf_total = {}
    finger_position = np.array([0., 0, 1.5])
    finger_target = finger_position.copy()
    pointer = None
    pointer_scene = None
    finger_mocap_id = None
    finger_geom_id = None
    eye_ids = [
        mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_CAMERA, element.name)
        for element in fly.eyecameraname_to_mjcfcamera.values()
    ] if vision else []
    eye_looming = {eye: SphereLooming() for eye in eye_ids}
    target_geom_id = None
    object_ids = {}
    objects = Objects(environment.half_size_mm)
    cursor_valid = False
    interaction_error = None
    browser_inputs = BrowserInputs() if browser_app else None
    browser_pointer = None
    timings = PhaseTimings()
    if virtual_finger:
        finger_body_id = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_BODY, "virtual_finger")
        finger_mocap_id = sim.mj_model.body_mocapid[finger_body_id]
        finger_geom_id = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, "virtual_finger_tip")
        target_geom_id = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, "pointer_target")
        object_ids = {
            name: mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, name) for name, _, _ in SLOTS
        }
        if objects_path:
            objects.load(objects_path)
            for item in objects.placements:
                sim.mj_model.geom_pos[object_ids[item["name"]]] = item["position_mm"]
            mj.mj_forward(sim.mj_model, sim.mj_data)
        if finger_mocap_id < 0 or finger_geom_id < 0:
            raise RuntimeError("Virtual finger body/geometry missing")
    if feeding:
        sugar_geom = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, "sugar_exposure_region")
        readout_geom = mj.mj_name2id(sim.mj_model, mj.mjtObj.mjOBJ_GEOM, "mn9_readout_marker")
        if min(sugar_geom, readout_geom) < 0:
            raise ValueError("Neural feeding visual markers missing from compiled scene")
    visual_activity = None
    steps_per_frame = max(1, round((1 / 60) / sim.timestep))
    output.mkdir(parents=True)
    (output / "status.json").write_text('{"status": "running"}\n')
    (output / "environment.json").write_text(json.dumps(environment_dict(environment), indent=2) + "\n")
    (output / "schedule.json").write_text(json.dumps(schedule, indent=2) + "\n")
    if virtual_finger:
        (output / "objects.json").write_text(json.dumps(objects.placements, indent=2) + "\n")
    trajectory_stream = (output / "trajectory.csv").open("w", newline="")
    sensor_stream = (output / "sensors.jsonl").open("w")
    vision_stream = (output / "vision.jsonl").open("w") if vision else None
    trajectory_writer = csv.writer(trajectory_stream)
    trajectory_writer.writerow(["time_s", "episode", "x_mm", "y_mm", "z_mm", "left_drive", "right_drive", "contacts"])

    def frame():
        nonlocal simulated, completed_steps, bump_until, schedule_index, episode, latest_observation, latest_motor
        nonlocal sensor_count
        nonlocal close_requested
        nonlocal next_vision_s, eye_frames, vision_samples, fallen_observation_frames
        nonlocal eye_time_s, dashboard_vision_samples
        nonlocal visual_activity
        nonlocal brain_records, brain_mn9_spikes, brain_network_spikes, brain_state, exposure
        nonlocal neural_episode_start
        nonlocal looming_state
        nonlocal interaction_error
        while schedule_index < len(schedule) and schedule[schedule_index]["time_s"] <= simulated:
            commands.put(ord(schedule[schedule_index]["key"]))
            schedule_index += 1
        while not commands.empty():
            code = commands.get()
            requested_key = chr(code).upper() if 0 <= code < 256 else ""
            if controls.autonomous and requested_key in {"W", "S", "A", "D", "X", "N"}:
                events.append({
                    "simulated_seconds": simulated, "episode": episode,
                    "key": requested_key, "ignored": True,
                    "reason": "Direct steering and controller selection are absent in the autonomous habitat",
                })
                print(
                    "WARNING: this habitat accepts environment changes, not direct steering or mode selection.",
                    file=sys.stderr, flush=True,
                )
                continue
            key = controls.key(code)
            if key is not None:
                interaction_error = None
                if key == "Q":
                    close_requested = True
                if key == "R":
                    reset()
                    episode += 1
                    bump_until = simulated
                    next_vision_s = simulated
                    visual_activity = None
                    recovery.reset(simulated)
                    for eye_state in eye_looming.values():
                        eye_state.previous_angle = None
                    if brain_client is not None:
                        brain_state = brain_client.reset()
                        neural_episode_start = simulated
                        neural_stream.write(json.dumps({
                            "op": "reset", "habitat_time_s": simulated, "episode": episode,
                            "brain_response": brain_state,
                        }) + "\n")
                        neural_stream.flush()
                        if dashboard is not None:
                            dashboard.publish({**brain_state, "habitat_time_s": simulated})
                elif key == "B":
                    bump_until = simulated + 0.05
                elif key in {"1", "2", "3"}:
                    try:
                        if not virtual_finger:
                            raise ValueError("Object placement requires virtual-finger scene support")
                        if key == "3":
                            placement = objects.remove()
                            sim.mj_model.geom_pos[object_ids[placement["name"]]] = [0, 0, -10]
                        else:
                            if not cursor_valid:
                                raise ValueError("Move the pointer over the arena before placing an object")
                            placement = objects.place("box" if key == "1" else "sphere", finger_target.tolist())
                            sim.mj_model.geom_pos[object_ids[placement["name"]]] = placement["position_mm"]
                        events.append({"simulated_seconds": simulated, "object_action": key, "object": placement})
                        (output / "objects.json").write_text(json.dumps(objects.placements, indent=2) + "\n")
                    except ValueError as error:
                        interaction_error = str(error)
                        events.append({"simulated_seconds": simulated, "object_action": key, "error": str(error)})
                        print(f"WARNING: object edit rejected: {error}", file=sys.stderr, flush=True)
                events.append({
                    "simulated_seconds": simulated, "episode": episode,
                    "key": key, **asdict(controls),
                })
                sim.mj_model.geom_pos[obstacle_ids] = obstacle_positions
                if not controls.obstacles:
                    sim.mj_model.geom_pos[obstacle_ids, 2] = -10
                sim.mj_model.geom_friction[ground_id] = original_friction
                if controls.slippery:
                    sim.mj_model.geom_friction[ground_id, 0] = 0.1
                mj.mj_forward(sim.mj_model, sim.mj_data)
        if controls.paused or close_requested:
            if dashboard is not None and brain_state is not None:
                dashboard.publish({
                    **brain_state, "habitat_time_s": simulated,
                    **({"eye_time_s": eye_time_s} if eye_time_s is not None else {}),
                    "paused": controls.paused, "status": "paused" if controls.paused else "closing",
                    "environment_controls": asdict(controls), "interaction_error": interaction_error,
                    "editable_objects": len(objects.placements), "virtual_finger_available": virtual_finger,
                })
            return
        interval_steps = steps_per_frame if target_steps is None else min(
            steps_per_frame, target_steps - completed_steps
        )
        interval_start = simulated
        if virtual_finger:
            enabled = controls.finger_enabled and (browser_app or pointer is not None)
            if enabled:
                delta = finger_target - finger_position
                length = np.linalg.norm(delta)
                max_move = 20 * interval_steps * sim.timestep
                finger_position[:] += delta * min(1, max_move / length) if length else 0
                sim.mj_data.mocap_pos[finger_mocap_id] = finger_position
                sim.mj_model.geom_rgba[finger_geom_id, 3] = 1
            else:
                sim.mj_data.mocap_pos[finger_mocap_id] = [0, 0, -10]
                sim.mj_model.geom_rgba[finger_geom_id, 3] = 0
            mj.mj_forward(sim.mj_model, sim.mj_data)
            distance = float(np.linalg.norm(finger_position - sim.mj_data.xpos[body_id]))
            views = finger_visibility(
                sim.mj_model, sim.mj_data, finger_geom_id, finger_position, 1.5,
                eye_ids, body_id,
            ) if eye_ids and enabled else []
            per_eye = []
            by_eye = {view["camera_id"]: view for view in views}
            for eye, eye_state in eye_looming.items():
                view = by_eye.get(eye)
                features = eye_state.sample(
                    view["distance_mm"] if view else distance, 1.5,
                    interval_steps * sim.timestep, enabled,
                    view["visible"] if view else False,
                )
                per_eye.append({**(view or {"camera_id": int(eye)}), **features})
            looming_state = {
                "looming_active": any(feature["looming_active"] for feature in per_eye),
                "eye_views": per_eye,
                "encoder": "per-eye spherical features; uncalibrated binary broadcast to both visual populations",
            }
            looming_state["eye_camera_visibility_available"] = bool(eye_ids)
            looming_state["finger_position_mm"] = finger_position.tolist()
            looming_state["finger_enabled"] = enabled
            looming_state["pointer_target_mm"] = finger_target.tolist()
            looming_state["pointer_lag_mm"] = float(np.linalg.norm(finger_target - finger_position))
        if brain_client is not None:
            probe = sim.mj_data.xpos[body_id] + sim.mj_data.xmat[body_id].reshape(3, 3) @ np.array(feeding.probe_mm)
            exposure = feeding.exposure(probe.tolist(), controls.sugar_enabled)
            sim.mj_model.geom_rgba[sugar_geom, 3] = 0.15 if controls.sugar_enabled else 0.02
            brain_client.begin_step(
                interval_steps * sim.timestep * 1000, exposure["sugar_contact"],
                looming_state["looming_active"],
            )
        latest_observation = sample_environment(
            sim, fly, body_id, environment, simulated, episode
        )
        if latest_observation.uprightness < 0.25:
            fallen_observation_frames += 1
        if vision and simulated >= next_vision_s:
            with timings.measure("eye_render_fisheye"):
                eye_frames = sim.get_raw_vision(fly.name)
            eye_time_s = simulated
            if eye_frames.ndim != 4 or eye_frames.shape[0] != 2 or not np.isfinite(eye_frames).all():
                raise RuntimeError("Invalid rendered eye observations")
            with timings.measure("retinal_channels"):
                retina = np.stack([
                    sim.retina.raw_image_to_hex_pxls(eye) for eye in eye_frames
                ])
            vision_stream.write(json.dumps({
                "time_s": simulated, "episode": episode,
                "shape": list(retina.shape), "ommatidia_channels": retina.tolist(),
                "controller_uses_visual_input": controls.sensory,
            }, allow_nan=False) + "\n")
            vision_stream.flush()
            vision_samples += 1
            visual_activity = tuple(float(eye.mean()) / 255 for eye in retina)
            next_vision_s = simulated + 0.1
        if visual_activity is not None:
            latest_observation = replace(
                latest_observation, visual_activity_left=visual_activity[0],
                visual_activity_right=visual_activity[1],
            )
        latest_motor = (
            sensory_command(latest_observation, controls.drive) if controls.sensory
            else controls.motor_command()
        )
        wind_force = environment.wind_force(latest_observation.velocity_mm_s)
        sensor_stream.write(json.dumps({
            "observation": asdict(latest_observation),
            "motor_command": asdict(latest_motor),
            "controller": "autonomous-hybrid" if controls.autonomous else ("sensory-demo" if controls.sensory else "manual"),
            "wind_force_uN": wind_force,
            "recovery_phase": recovery.phase if self_righting else "disabled",
        }, allow_nan=False) + "\n")
        sensor_count += 1
        for _ in range(steps_per_frame):
            if target_steps is not None and completed_steps >= target_steps:
                break
            sim.mj_data.xfrc_applied[body_id] = 0
            sim.mj_data.xfrc_applied[body_id, :3] = [
                WALKING_UNITS.force_from_micro_newtons(value) for value in wind_force
            ]
            if simulated < bump_until:
                sim.mj_data.xfrc_applied[body_id, 1] += WALKING_UNITS.force_from_micro_newtons(5.0)
            obs = gait_reader.read() if gait_reader is not None else HybridControllerObservation.from_sim(sim, fly.name)
            phase_before = recovery.phase
            phase = recovery.update(
                simulated, float(sim.mj_data.xmat[body_id].reshape(3, 3)[2, 2])
            ) if self_righting else "idle"
            if phase == "push":
                from flygym_demo.complex_terrain import LocomotionAction
                scale = min((simulated - recovery.phase_start) / 0.1, 1)
                action = LocomotionAction(neutral + offsets * scale, np.zeros(6, dtype=bool))
            elif phase == "failed":
                from flygym_demo.complex_terrain import LocomotionAction
                action = LocomotionAction(neutral, np.zeros(6, dtype=bool))
            else:
                if phase_before == "push" and phase == "stabilize":
                    controller.reset(seed=0)
                drive = np.ones(2) if phase == "stabilize" else np.array([
                    latest_motor.left_drive, latest_motor.right_drive,
                ])
                action = controller.step(drive, obs)
            apply_locomotion_action(sim, fly.name, action)
            sim.step()
            completed_steps += 1
            simulated = completed_steps * sim.timestep
        if not np.isfinite(sim.mj_data.qpos).all() or not np.isfinite(sim.mj_data.qvel).all():
            raise RuntimeError("Non-finite biomechanical state; simulation stopped")
        pos = sim.get_body_positions(fly.name)[thorax]
        trajectory_writer.writerow([
            simulated, episode, *pos.tolist(),
            latest_motor.left_drive, latest_motor.right_drive, sim.mj_data.ncon,
        ])
        if brain_client is not None:
            with timings.measure("neural_wait_validation"):
                brain_state = brain_client.finish_step()
            expected_time = (simulated - neural_episode_start) * 1000
            if abs(brain_state["brain_time_ms"] - expected_time) > 1e-5:
                raise RuntimeError("Neural and habitat simulated clocks have diverged")
            brain_records += 1
            brain_mn9_spikes += brain_state["mn9_spikes"]
            brain_network_spikes += brain_state["network_spikes"]
            for value, count in brain_state["giant_fiber_spikes"].items():
                gf_total[value] = gf_total.get(value, 0) + count
            neural_stream.write(json.dumps({
                "op": "step", "habitat_start_s": interval_start, "habitat_end_s": simulated,
                "episode": episode, "exposure": exposure, "brain_response": brain_state,
                "locomotion_controller": "autonomous-hybrid" if controls.autonomous else ("sensory-demo" if controls.sensory else "manual"),
                "mn9_drives_locomotion": False,
                "looming": looming_state,
            }, allow_nan=False) + "\n")
            neural_stream.flush()
            if dashboard is not None:
                dashboard.publish(
                    {
                        **brain_state, "habitat_time_s": simulated,
                        **({"eye_time_s": eye_time_s} if eye_time_s is not None else {}),
                        "paused": controls.paused, "status": "running",
                        "environment_controls": asdict(controls), "interaction_error": interaction_error,
                        "editable_objects": len(objects.placements), "virtual_finger_available": virtual_finger,
                    },
                    np.concatenate(eye_frames, axis=1).astype(np.uint8)
                    if eye_frames is not None and vision_samples != dashboard_vision_samples else None,
                )
                dashboard_vision_samples = vision_samples
            probe = sim.mj_data.xpos[body_id] + sim.mj_data.xmat[body_id].reshape(3, 3) @ np.array(feeding.probe_mm)
            sim.mj_model.geom_pos[readout_geom] = probe
            sim.mj_model.geom_rgba[readout_geom] = (
                [1, 0.15, 0.1, 1] if brain_state["feeding_circuit_active"] else [0.4, 0.4, 0.4, 1]
            )
            mj.mj_forward(sim.mj_model, sim.mj_data)
        sensor_stream.flush()
        trajectory_stream.flush()

    started = time.perf_counter()
    viewer = None
    state_guard = None
    presentation = ObserverScene(sim.mj_model, sim.mj_data) if observer_graphics and not browser_app else None
    neural_episode_start = 0.0
    try:
        if feeding is not None:
            print("Loading actual FlyWire-630 network; locomotion remains separate.", flush=True)
            brain_client = BrainClient(
                brain_python, brain_data_dir, output, feeding.seed,
                takeoff=virtual_finger, telemetry=neural_dashboard,
            )
            brain_metadata = brain_client.metadata
            (output / "brain-metadata.json").write_text(json.dumps({
                **brain_metadata, "config": json.loads(brain_feeding.read_text()),
                "config_sha256": hashlib.sha256(brain_feeding.read_bytes()).hexdigest(),
                **feeding_provenance,
            }, indent=2) + "\n")
            neural_stream = (output / "neural-feeding.jsonl").open("x")
            if neural_dashboard:
                from fly_dashboard import Dashboard
                from fly_connections import ConnectionIndex
                connections = ConnectionIndex(
                    brain_metadata["connection_index_dir"], brain_metadata["neuron_ids"],
                    brain_metadata["upstream_commit"],
                )
                dashboard = Dashboard(
                    output, brain_metadata, port=dashboard_port, connections=connections,
                    inputs=browser_inputs,
                )
                print(f"Neuron dashboard: {dashboard.url}", flush=True)
        if browser_app:
            with WorldRenderer(
                sim.mj_model, sim.mj_data, environment.half_size_mm, body_id,
                browser_inputs, dashboard.publish_world, graphics=observer_graphics,
            ) as renderer:
                last_profile_write = 0.0
                while not close_requested and (target_steps is None or completed_steps < target_steps):
                    renderer.check()
                    while not browser_inputs.empty():
                        event = browser_inputs.get_nowait()
                        events.append({"browser_input": event, "simulated_seconds": simulated, "episode": episode})
                        if event["kind"] == "key":
                            commands.put(ord(event["key"]))
                        elif event["kind"] == "pointer":
                            browser_pointer = (event["x"]*1280, (1-event["y"])*960)
                        else:
                            controls.follow_camera = False
                    if virtual_finger and browser_pointer is not None:
                        target = renderer.target(*browser_pointer)
                        cursor_valid = target is not None
                        if cursor_valid:
                            finger_target[:] = target
                            finger_target[:2] = np.clip(finger_target[:2], -environment.half_size_mm+1.5, environment.half_size_mm-1.5)
                            sim.mj_model.geom_pos[target_geom_id] = finger_target
                        sim.mj_model.geom_rgba[target_geom_id, 3] = 1 if cursor_valid else 0
                    with timings.measure("coupled_body_neural_interval"):
                        frame()
                    now = time.perf_counter()
                    with timings.measure("submit_observer_snapshot"):
                        renderer.submit(sim.mj_model, sim.mj_data, simulated, controls.follow_camera)
                    if now-last_profile_write >= 1 or close_requested:
                        (output / "performance.json").write_text(json.dumps({
                            "phases": timings.snapshot(), "simulated_seconds": simulated,
                            "wall_seconds":time.perf_counter()-started,
                            "world_resolution":[1280,960], "render_publication_cap_Hz":30,
                            "cached_gait_observation":cached_gait_observation,
                            "independent_world_renderer":renderer.metrics(),
                            "scope":"Wall-time phase totals; not GPU-kernel timing or p95 input latency.",
                        },indent=2)+"\n")
                        last_profile_write=now
                    if controls.paused:
                        time.sleep(0.02)
            # Source clocks/counts remain authoritative; rendering never steps physics.
        elif headless:
            while completed_steps < target_steps:
                frame()
        else:
            state_guard = ViewerStateGuard(sim.mj_model, sim.mj_data)
            with managed_viewer(
                presentation.model if presentation else sim.mj_model,
                presentation.data if presentation else sim.mj_data,
                key_callback=commands.put,
                show_left_ui=False, show_right_ui=False,
            ) as viewer:
                if virtual_finger:
                    pointer = Pointer()
                    pointer_scene = mj.MjvScene(sim.mj_model, maxgeom=10000)
                viewer.cam.type = mj.mjtCamera.mjCAMERA_FREE
                viewer.cam.lookat[:] = initial
                viewer.cam.trackbodyid = body_id
                viewer.cam.distance = environment.half_size_mm if scene is not None else 12
                viewer.cam.azimuth = 135
                viewer.cam.elevation = -25
                while viewer.is_running() and not close_requested and (target_steps is None or completed_steps < target_steps):
                    frame_started = time.perf_counter()
                    with viewer.lock():
                        state_guard.restore_if_changed()
                        if pointer is not None:
                            cursor = pointer.position(viewer.viewport)
                            cursor_valid = cursor is not None
                            if cursor is not None:
                                mj.mjv_updateScene(
                                    sim.mj_model, sim.mj_data, viewer.opt, None,
                                    viewer.cam, mj.mjtCatBit.mjCAT_ALL, pointer_scene,
                                )
                                camera = mj.mjv_averageCamera(pointer_scene.camera[0], pointer_scene.camera[1])
                                target = pointer_target(camera, viewer.viewport, *cursor)
                                if target is not None:
                                    finger_target[:] = target
                                    finger_target[:2] = np.clip(
                                        finger_target[:2], -environment.half_size_mm + 1.5,
                                        environment.half_size_mm - 1.5,
                                    )
                                    sim.mj_model.geom_pos[target_geom_id] = finger_target
                                    sim.mj_model.geom_rgba[target_geom_id, 3] = 1
                                else:
                                    cursor_valid = False
                            if not cursor_valid:
                                sim.mj_model.geom_rgba[target_geom_id, 3] = 0
                        frame()
                        if presentation is not None:
                            presentation.sync()
                        state_guard.capture()
                        viewer.cam.type = (
                            mj.mjtCamera.mjCAMERA_TRACKING if controls.follow_camera else
                            mj.mjtCamera.mjCAMERA_FREE
                        )
                    elapsed = time.perf_counter() - started
                    throughput = simulated / elapsed if elapsed else 0
                    viewer.set_texts([(
                        mj.mjtFontScale.mjFONTSCALE_100, mj.mjtGridPos.mjGRID_TOPLEFT,
                        control_help(controls.autonomous),
                        f"Sim {simulated:.2f}s | {throughput:.2f}x measured\n"
                        f"Session {'until window closes' if until_closed else 'bounded test'}\n" +
                        (f"Automatic environment response\n" if controls.autonomous else
                         f"Drive {controls.drive:.1f} Turn {controls.turn:.1f}\n") +
                        f"Terrain {'on' if controls.obstacles else 'off'} "
                        f"Friction {'low' if controls.slippery else 'normal'}\n"
                        f"Playback {controls.playback:.2f}x "
                        f"{'PAUSED' if controls.paused else ''}\n"
                        f"Locomotion {'engineered autonomous' if controls.autonomous else ('sensory-demo' if controls.sensory else 'manual')}\n"
                        f"Pose {'FALLEN' if latest_observation.uprightness < 0.25 else 'upright'} "
                        f"Recovery {recovery.phase if self_righting else 'disabled'}\n"
                        f"Odor L/R {latest_observation.odor_left:.3f}/{latest_observation.odor_right:.3f}\n"
                        f"Ranges L/F/R {latest_observation.range_left_mm:.1f}/"
                        f"{latest_observation.range_forward_mm:.1f}/"
                        f"{latest_observation.range_right_mm:.1f} mm\n"
                        f"Feeding {'LIVE FlyWire spikes' if brain_client else 'not connected'}\n"
                        f"Sugar {'contact' if exposure and exposure['sugar_contact'] else 'absent/outside'} "
                        f"MN9 {(brain_state or {}).get('mn9_rate_Hz', 0):.1f} Hz\n"
                        f"Finger {'enabled' if controls.finger_enabled else 'off'} "
                        f"Approach {looming_state['looming_active']}\n"
                        f"Pointer lag {looming_state.get('pointer_lag_mm', 0):.2f} mm | objects {len(objects.placements)}/6\n"
                        f"GF spikes {(brain_state or {}).get('giant_fiber_spikes', {})}\n"
                        "GF is a live neural readout, NOT physical takeoff",
                    )])
                    if eye_frames is not None:
                        from PIL import Image
                        eyes = np.concatenate(eye_frames, axis=1).astype(np.uint8)
                        bounds = eye_inset_bounds(
                            viewer.viewport.left, viewer.viewport.bottom,
                            viewer.viewport.width, viewer.viewport.height,
                        )
                        inset = np.asarray(Image.fromarray(eyes).resize(bounds[2:]))
                        viewer.set_images((mj.MjrRect(*bounds), inset))
                    viewer.sync()
                    target = (steps_per_frame * sim.timestep) / controls.playback
                    time.sleep(max(0, target - (time.perf_counter() - frame_started)))
                with viewer.lock():
                    state_guard.restore_if_changed()
        elapsed = time.perf_counter() - started
        final = sim.get_body_positions(fly.name)[thorax].copy()
        (output / "events.json").write_text(json.dumps(events, indent=2) + "\n")
        (output / "objects.json").write_text(json.dumps(objects.placements, indent=2) + "\n")
        summary = {
            "status": "completed" if completed_steps == target_steps else "closed_by_user",
            "browser_app": browser_app,
            "cached_gait_observation": cached_gait_observation,
            "framework": "NeuroMechFly / FlyGym", "upstream_commit": REVISION,
            "controller": "upstream hybrid CPG/reflex position controller; NOT connectome-driven",
            "flygym": importlib.metadata.version("flygym"),
            "mujoco": importlib.metadata.version("mujoco"),
            **CODE_HASHES,
            "environment_sha256": hashlib.sha256(json.dumps(
                environment_dict(environment), sort_keys=True
            ).encode()).hexdigest(),
            "schedule_sha256": hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest(),
            "headless": headless, "requested_simulated_seconds": None if until_closed else seconds,
            "native_physics_edits_rejected": state_guard.rejections if state_guard else 0,
            "until_closed": until_closed,
            "simulated_seconds": simulated, "wall_seconds": elapsed,
            "throughput": simulated / elapsed,
            "displacement_mm": (final - initial).tolist(),
            "initial_position_mm": initial.tolist(), "final_position_mm": final.tolist(),
            "controls": asdict(controls), "events": len(events),
            "timestep_s": sim.timestep, "model_bodies": sim.mj_model.nbody,
            "requested_physics_steps": target_steps, "completed_physics_steps": completed_steps,
            "model_actuators": sim.mj_model.nu,
            "environment": environment_dict(environment),
            "controller_mode": "autonomous-hybrid" if controls.autonomous else ("sensory-demo" if controls.sensory else "manual"),
            "environment_only_interaction": controls.autonomous,
            "fully_connectome_controlled": False,
            "placed_objects": objects.placements,
            "observer_graphics": {
                "enabled": observer_graphics,
                "affects_physics": False, "affects_retinal_input": False,
                "features": ["8192 shadow map", "4x offscreen MSAA", "observer headlight", "body/eye/wing materials", "reduced floor reflectance"]
                    if observer_graphics else [],
            },
            "schedule_events_applied": schedule_index,
            "schedule_events_requested": len(schedule),
            "episode_resets": episode,
            "sensory_records": sensor_count,
            "vision_enabled": vision, "vision_samples": vision_samples,
            "visual_controller_connected": bool(vision and controls.sensory),
            "visual_policy": "engineered normalized bilateral retinal-intensity steering; not biological motion/optic-flow circuitry",
            "fallen_observation_frames": fallen_observation_frames,
            "recovery_controller_available": self_righting,
            "recovery": {
                "experimental": True, "phase": recovery.phase, "attempts": recovery.attempts,
                "successes": recovery.successes, "failures": recovery.failures,
                "events": recovery.events, "uses_pose_reset": False,
                "offsets_rad": offsets.tolist(),
                "calibration": "deterministic bounded candidate search, seed 422; tuned to this model/habitat, not measured animal recovery",
            } if self_righting else None,
            "initial_diagnostic_roll_deg": initial_roll_deg,
            "neural_feeding": {
                "enabled": feeding is not None, "metadata": brain_metadata,
                "intervals": brain_records, "mn9_spikes": brain_mn9_spikes,
                "network_spikes": brain_network_spikes, "locomotion_driven_by_brain": False,
                "physical_proboscis_connected": False,
                "giant_fiber_spikes": gf_total, "virtual_finger": virtual_finger,
                "physical_takeoff_connected": False,
            },
            "limitations": [
                "Odor/light channels are uncalibrated static Gaussian proxies sampled at approximate head offsets.",
                "Ray distances are engineered range sensing, not compound-eye vision.",
                "Wind uses capped linear drag on thorax, not wing aerodynamics or CFD.",
                "MotorCommand controls CPG drive, not measured descending-neuron firing.",
                "Aerodynamic flight is not supported by this walking engine.",
                "Visual behavior is engineered normalized retinal-intensity steering, not connectomic visual processing.",
                "Optional self-righting is an experimental actuator-only maneuver; general or biological validity is not established.",
            ],
        }
        if self_righting and recovery.failures:
            print(
                "WARNING: experimental self-righting failed; state/attempt history is saved. "
                "No automatic body reset was performed.",
                file=sys.stderr,
            )
        if headless:
            if presentation:
                presentation.sync()
            with mj.Renderer(presentation.model if presentation else sim.mj_model, height=480, width=640) as renderer:
                camera = mj.MjvCamera()
                camera.type = mj.mjtCamera.mjCAMERA_TRACKING
                camera.trackbodyid = body_id
                camera.distance = 12
                camera.azimuth = 135
                camera.elevation = -25
                renderer.update_scene(presentation.data if presentation else sim.mj_data, camera)
                from PIL import Image
                Image.fromarray(renderer.render()).save(output / "preview.png")
        if eye_frames is not None:
            from PIL import Image
            Image.fromarray(np.concatenate(eye_frames, axis=1).astype(np.uint8)).save(output / "eyes.png")
        if brain_client is not None:
            brain_client.close()
            brain_client = None
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "status.json").write_text(json.dumps({"status": summary["status"]}) + "\n")
        print(json.dumps(summary, indent=2))
    except Exception as error:
        (output / "status.json").write_text(json.dumps({
            "status": "failed", "error": str(error), "simulated_seconds": simulated,
        }) + "\n")
        raise
    finally:
        if dashboard is not None:
            dashboard.close()
        if brain_client is not None:
            brain_client.abort()
        if neural_stream is not None:
            neural_stream.close()
        trajectory_stream.close()
        sensor_stream.close()
        if vision_stream is not None:
            vision_stream.close()
        if sim.eye_renderer is not None:
            sim.eye_renderer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=60.0, help="Simulated duration, excluding pauses")
    parser.add_argument("--headless", action="store_true", help="Benchmark without viewer; write a rendered preview")
    parser.add_argument("--scene", type=Path, help="Version-1 habitat JSON; omit for original flat/bar scene")
    parser.add_argument("--schedule", type=Path, help="Simulated-time keyboard perturbation schedule")
    parser.add_argument("--controller", choices=["manual", "sensory-demo"], default="manual")
    parser.add_argument("--until-closed", action="store_true", help="Keep habitat simulation running until the viewer closes; stream observations to disk")
    parser.add_argument("--vision", action="store_true", help="Render eye views and retinal channels at 10 Hz; adds rendering cost, not a visual brain controller")
    parser.add_argument("--self-righting", action="store_true", help="Enable experimental leg-only recovery with sustained-uprightness checks")
    parser.add_argument("--initial-roll-deg", type=float, default=0, help="Explicit initial roll for recovery diagnostics; never used for automatic recovery")
    parser.add_argument("--brain-feeding", type=Path, help="Connect actual FlyWire spikes to this taste-exposure/readout config")
    parser.add_argument("--brain-data-dir", type=Path, help="External root containing verified original FlyWire inputs")
    parser.add_argument("--brain-python", type=Path, default=ROOT / ".venv/bin/python", help="Python interpreter from the pinned Brian 2 environment")
    parser.add_argument("--drive", type=float, default=1.0, help="Initial independent locomotion drive")
    parser.add_argument("--observer-graphics", action="store_true", help="Higher-quality observer rendering without changing physics or fly sensory images")
    parser.add_argument("--virtual-finger", action="store_true", help="X11 pointer-controlled physical finger and approximate live looming-to-GF diagnostic")
    parser.add_argument("--objects", type=Path, help="Reload supported saved object placements; requires virtual-finger")
    parser.add_argument("--neural-dashboard", action="store_true", help="Loopback companion with eyes and actual sparse neuron spike counts")
    parser.add_argument("--dashboard-port", type=int, default=DEFAULT_PORT, help="Companion port; 0 explicitly requests an ephemeral test port")
    args = parser.parse_args()
    try:
        run(
            args.output_dir, args.seconds, args.headless, args.scene,
            args.schedule, args.controller == "sensory-demo",
            args.until_closed,
            args.vision,
            args.self_righting, args.initial_roll_deg,
            args.brain_feeding, args.brain_data_dir, args.brain_python, args.drive,
            observer_graphics=args.observer_graphics,
            virtual_finger=args.virtual_finger,
            objects_path=args.objects,
            neural_dashboard=args.neural_dashboard,
            dashboard_port=args.dashboard_port,
        )
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
