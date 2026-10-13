"""FlyBody aerodynamic flight diagnostics, without a trained or connectomic policy."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import queue
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from zipfile import ZipFile

from datasets import CATALOG, ROOT
from fly_policy import (
    PublishedFlightPolicy, evaluate_tracking, prepare_tflite_policy, tracking_errors,
    verified_archive,
)
from sim_units import FLIGHT_UNITS, simulation_steps
from fly_environment import Environment, environment_dict
from fly_flight_arena import make_arena, sample_habitat
from sim_viewer import managed_viewer, ViewerStateGuard


REVISION = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
MEMBERS = {
    "flight-dataset_saccade-evasion_augmented.hdf5": 14292224,
    "wing_pattern_fmech.npy": 6128,
}


@dataclass
class FlightCommand:
    frequency: float = 0.0
    differential_roll: float = 0.0

    def validate(self):
        for value, limit in [(self.frequency, 1), (self.differential_roll, 0.2)]:
            if not math.isfinite(value) or not -limit <= value <= limit:
                raise ValueError("Flight frequency or differential wing-roll command is out of range")

    def key(self, code):
        key = "P" if code == 32 else (chr(code).upper() if 0 <= code < 256 else "")
        if key == "W":
            self.frequency = min(1, self.frequency + 0.1)
        elif key == "S":
            self.frequency = max(-1, self.frequency - 0.1)
        elif key == "A":
            self.differential_roll = min(0.2, self.differential_roll + 0.02)
        elif key == "D":
            self.differential_roll = max(-0.2, self.differential_roll - 0.02)
        elif key == "X":
            self.frequency = self.differential_roll = 0
        elif key != "P":
            return None
        self.validate()
        return key

    def values(self, names: list[str]) -> list[float]:
        self.validate()
        required = {"user_0", "wing_roll_left", "wing_roll_right"}
        if not required <= set(names) or len(names) != len(set(names)):
            raise ValueError("Flight action names do not match the pinned wing/frequency interface")
        values = [0.0] * len(names)
        values[names.index("user_0")] = self.frequency
        values[names.index("wing_roll_left")] = self.differential_roll
        values[names.index("wing_roll_right")] = -self.differential_roll
        return values


def viewer_status(paused: bool, current: float, duration: float, finished: bool = False, failed: bool = False) -> str:
    if finished:
        return "STOPPED: inspect/Q closes" if failed else "DONE: inspect/Q closes"
    if paused:
        return "PAUSED: P/Space starts"
    return f"FLYING {current:.2f}/{duration:.2f}s"


def wing_input_allowed(code: int, controller: str, allow_overrides: bool) -> bool:
    key = chr(code).upper() if 0 <= code < 256 else ""
    return controller != "trained" or allow_overrides or key not in {"W", "S", "A", "D"}


def prepare_data(data_dir: Path) -> dict[str, Path]:
    archive_path, root, asset, dataset = verified_archive(data_dir, CATALOG)
    extracted = root / "extracted"
    if extracted.is_symlink():
        raise ValueError("Extracted flight data directory must not be a symlink")
    extracted.mkdir(exist_ok=True)
    paths = {}
    manifest = {}
    with ZipFile(archive_path) as archive:
        if {entry.filename for entry in archive.infolist()} != set(MEMBERS):
            raise ValueError("Flight archive members differ from inspected upstream snapshot")
        for name, expected_size in MEMBERS.items():
            if archive.getinfo(name).file_size != expected_size:
                raise ValueError(f"Unexpected uncompressed size: {name}")
            payload = archive.read(name)
            target = extracted / name
            sha256 = hashlib.sha256(payload).hexdigest()
            if target.is_symlink():
                raise ValueError("Extracted flight files must not be symlinks")
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha256:
                    raise ValueError(f"Previously extracted data changed: {name}")
            else:
                with target.open("xb") as stream:
                    stream.write(payload)
            paths[name] = target
            manifest[name] = {"size_bytes": len(payload), "sha256": sha256}
    provenance = {
        "archive_checksum": asset["checksum"], "members": manifest,
        "license": dataset["license"], "source_ids": dataset["source_ids"],
    }
    receipt_path = extracted / "extraction.json"
    if receipt_path.is_symlink():
        raise ValueError("Flight extraction manifest must not be a symlink")
    if receipt_path.exists():
        if json.loads(receipt_path.read_text()) != provenance:
            raise ValueError("Existing flight extraction manifest does not match source")
    else:
        with receipt_path.open("x") as stream:
            stream.write(json.dumps(provenance, indent=2) + "\n")
    return paths


def goal_environment(paths, seconds, seed, speed_cm_s, height_cm, yaw_rate_rad_s, arena=None):
    import numpy as np
    from dm_control import composer
    from dm_control.locomotion.arenas import floors
    from flybody.fruitfly.fruitfly import FruitFly
    from flybody.tasks.constants import _FLY_CONTROL_TIMESTEP
    from flybody.tasks.flight_imitation import FlightImitationWBPG
    from flybody.tasks.pattern_generators import WingBeatPatternGenerator
    from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
    from flybody.tasks.trajectory_loaders import InferenceFlightTrajectoryLoader

    steps = simulation_steps(seconds, _FLY_CONTROL_TIMESTEP)
    future_steps = 5
    total_steps = steps + future_steps + 1
    qpos, qvel = constant_speed_trajectory(
        n_steps=total_steps, speed=speed_cm_s, yaw_speed=yaw_rate_rad_s,
        init_pos=(0, 0, height_cm), body_rot_angle_y=-47.5,
        control_timestep=_FLY_CONTROL_TIMESTEP,
    )
    loader = InferenceFlightTrajectoryLoader()
    loader.set_next_trajectory(qpos, qvel)
    horizon = total_steps * _FLY_CONTROL_TIMESTEP
    task = FlightImitationWBPG(
        walker=FruitFly, arena=floors.Floor() if arena is None else arena,
        wbpg=WingBeatPatternGenerator(base_pattern_path=str(paths["wing_pattern_fmech.npy"])),
        traj_generator=loader, time_limit=horizon, terminal_com_dist=2.0,
        initialize_qvel=True, force_actuators=False, disable_legs=True,
        joint_filter=0, future_steps=future_steps,
    )
    return composer.Environment(
        time_limit=horizon, task=task, random_state=np.random.RandomState(seed),
        strip_singleton_obs_buffer_dim=True,
    )


def run(
    data_dir: Path, output: Path, seconds: float, headless: bool,
    start_paused: bool = False, controller: str = "diagnostic", seed: int = 0,
    trajectory: int = 0, gust_uN: float = 0, gust_at_s: float = 0.2,
    gust_duration_s: float = 0.05, reference: str = "measured",
    speed_cm_s: float = 20, height_cm: float = 1, yaw_rate_rad_s: float = 0,
    allow_wing_overrides: bool = False,
    scene_path: Path | None = None,
    exit_on_complete: bool = False,
):
    import mujoco as mj
    import numpy as np
    from flybody.fly_envs import flight_imitation

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in [data_dir, output]):
        raise ValueError("Flight inputs and results must stay outside Git")
    if output.exists():
        raise FileExistsError("Choose a new flight output directory")
    if reference not in {"measured", "straight-goal"}:
        raise ValueError("Unknown flight reference mode")
    duration_limit = 0.6 if reference == "measured" else 60
    if not math.isfinite(seconds) or not 0 < seconds <= duration_limit:
        raise ValueError(f"Duration must be between 0 and {duration_limit} simulated seconds")
    if (
        not math.isfinite(speed_cm_s) or not 0 <= speed_cm_s <= 100
        or not math.isfinite(height_cm) or not 0.5 <= height_cm <= 20
        or not math.isfinite(yaw_rate_rad_s) or abs(yaw_rate_rad_s) > 5
    ):
        raise ValueError("Flight goal speed/height/heading rate is outside supported numeric bounds")
    if headless and start_paused:
        raise ValueError("Headless flight cannot start paused")
    if controller not in {"diagnostic", "trained"} or seed < 0 or trajectory < 0:
        raise ValueError("Invalid controller, seed, or trajectory")
    if (
        not math.isfinite(gust_uN) or abs(gust_uN) > 20
        or not math.isfinite(gust_at_s) or gust_at_s < 0
        or not math.isfinite(gust_duration_s) or gust_duration_s <= 0
        or (gust_uN != 0 and gust_at_s + gust_duration_s > seconds)
    ):
        raise ValueError("Gust must be finite, within +/-20 microNewtons, and fit inside the run")
    paths = prepare_data(data_dir)
    habitat = Environment.load(scene_path) if scene_path is not None else None
    if habitat is not None and habitat.schema_version >= 3:
        raise ValueError("Movable grassland scenes require the unified FlyBody backend, not the legacy flight benchmark")
    if habitat is not None and reference != "straight-goal":
        raise ValueError("--scene currently requires --reference straight-goal; measured benchmarks remain unchanged")
    env = (
        flight_imitation(
            ref_path=str(paths["flight-dataset_saccade-evasion_augmented.hdf5"]),
            wpg_pattern_path=str(paths["wing_pattern_fmech.npy"]),
            traj_indices=[trajectory], randomize_start_step=False,
            random_state=np.random.RandomState(seed),
        ) if reference == "measured" else
        goal_environment(
            paths, seconds, seed, speed_cm_s, height_cm, yaw_rate_rad_s,
            make_arena(habitat) if habitat is not None else None,
        )
    )
    command = FlightCommand()
    commands = queue.SimpleQueue()
    events, observations = [], []
    control_records = []
    clipped_policy_components = 0
    policy_wall_seconds = 0.0
    physics_wall_seconds = 0.0
    paused = start_paused
    output.mkdir(parents=True)
    (output / "status.json").write_text('{"status": "running"}\n')
    started = time.perf_counter()
    timestep = None
    state_guard = None
    boundary_exit_steps = 0
    first_boundary_exit_s = None
    close_requested = False
    try:
        timestep = env.reset()
        target_steps = simulation_steps(seconds, env.control_timestep())
        reference_seconds = env.task._traj_timesteps * env.control_timestep()
        if seconds > reference_seconds + 1e-9:
            raise ValueError(
                f"Trajectory {trajectory} only supports {reference_seconds:.4f} seconds "
                f"after its required future-reference window; choose a shorter duration "
                f"or a longer measured trajectory"
            )
        policy = PublishedFlightPolicy(prepare_tflite_policy(data_dir, CATALOG)) if controller == "trained" else None
        spec = env.action_spec()
        names = spec.name.split("\t")
        if spec.shape != (len(names),):
            raise ValueError("Flight action specification shape disagrees with named controls")
        model, data = env.physics.model.ptr, env.physics.data.ptr
        if habitat is not None:
            for geom_id in range(model.ngeom):
                name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom_id) or ""
                if name.startswith(("walker/", "ghost/")):
                    model.geom_group[geom_id] = 1
            (output / "environment.json").write_text(json.dumps(environment_dict(habitat), indent=2) + "\n")
        body_id = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, "walker/thorax")
        if body_id < 0:
            raise ValueError("Expected FlyBody thorax missing")
        initial = data.xpos[body_id].copy()
        initial_orientation = data.xquat[body_id].copy()
        initial_wing_phase_index = int(env.task._wbpg._step)
        if model.opt.density <= 0 or not np.any(model.geom_fluid[:, 0] > 0):
            raise ValueError("Aerodynamic ellipsoid fluid interaction is not enabled")
        steps_per_frame = max(1, round((1 / 60) / env.control_timestep()))
        floor_ids = [
            i for i in range(model.ngeom)
            if mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i) == "groundplane"
        ]
        if len(floor_ids) != 1:
            raise ValueError("Expected exactly one groundplane for contact validation")
        floor_id = floor_ids[0]
        arena_contact_ids = {floor_id}
        if habitat is not None:
            arena_contact_ids.update(
                i for i in range(model.ngeom)
                if (mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i) or "") in {
                    terrain.name for terrain in habitat.terrain
                } or (mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i) or "").startswith("arena_wall_")
            )

        def frame():
            nonlocal timestep, paused, clipped_policy_components, policy_wall_seconds, physics_wall_seconds
            nonlocal boundary_exit_steps, first_boundary_exit_s
            nonlocal close_requested
            while not commands.empty():
                code = commands.get()
                if code == ord("Q"):
                    close_requested = True
                    continue
                if not wing_input_allowed(code, controller, allow_wing_overrides):
                    events.append({
                        "time_s": env.physics.time(), "key": chr(code).upper(),
                        "ignored": True, "reason": "raw wing overrides require --allow-wing-overrides",
                    })
                    print(
                        "WARNING: W/S/A/D are raw wing controls, not navigation keys. "
                        "The trained policy owns them unless --allow-wing-overrides is set.",
                        file=sys.stderr, flush=True,
                    )
                    continue
                key = command.key(code)
                if key is not None:
                    if key == "P":
                        paused = not paused
                    events.append({
                        "time_s": env.physics.time(), "key": key,
                        "paused": paused, "motor_command": asdict(command),
                    })
                    print(json.dumps(events[-1]), flush=True)
            if paused or len(control_records) >= target_steps or timestep.last():
                return
            for _ in range(steps_per_frame):
                if len(control_records) >= target_steps or timestep.last():
                    break
                residual = np.array(command.values(names))
                if policy is None:
                    action = residual
                else:
                    policy_started = time.perf_counter()
                    action, clipped = policy.action(timestep.observation, spec)
                    policy_wall_seconds += time.perf_counter() - policy_started
                    clipped_policy_components += clipped
                    action = np.clip(action + residual, spec.minimum, spec.maximum)
                if not np.all((action >= spec.minimum) & (action <= spec.maximum)):
                    raise ValueError("Flight motor command exceeds action bounds")
                control_time = len(control_records) * env.control_timestep()
                force_uN = gust_uN if gust_at_s <= control_time < gust_at_s + gust_duration_s else 0
                data.xfrc_applied[body_id] = 0
                wind_force = (0.0, 0.0, 0.0)
                if habitat is not None:
                    velocity = np.zeros(6)
                    mj.mj_objectVelocity(model, data, mj.mjtObj.mjOBJ_BODY, body_id, velocity, False)
                    wind_force = habitat.wind_force(velocity[3:] * 10)
                    data.xfrc_applied[body_id, :3] = [
                        FLIGHT_UNITS.force_from_micro_newtons(value) for value in wind_force
                    ]
                data.xfrc_applied[body_id, 1] += FLIGHT_UNITS.force_from_micro_newtons(force_uN)
                issued_action = action.copy()
                physics_started = time.perf_counter()
                timestep = env.step(action)
                physics_wall_seconds += time.perf_counter() - physics_started
                if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                    raise RuntimeError("Non-finite flight state")
                distance, angle = tracking_errors(timestep.observation)
                outside = habitat is not None and any(
                    abs(value * 10) > habitat.half_size_mm for value in data.xpos[body_id][:2]
                )
                if outside:
                    boundary_exit_steps += 1
                    if first_boundary_exit_s is None:
                        first_boundary_exit_s = env.physics.time()
                control_records.append({
                    "time_s": env.physics.time(), "position_error_cm": distance,
                    "orientation_error_deg": angle,
                    "floor_contacts": sum(
                        int(contact.geom1 == floor_id or contact.geom2 == floor_id)
                        for contact in data.contact[:data.ncon]
                    ),
                    "action": issued_action.tolist(),
                    "task_action_after_wingbeat": action.tolist(),
                    "lateral_force_uN": force_uN,
                    "wind_force_uN": wind_force,
                    "outside_habitat_xy_bounds": outside,
                    "arena_contacts": sum(
                        int(contact.geom1 in arena_contact_ids or contact.geom2 in arena_contact_ids)
                        for contact in data.contact[:data.ncon]
                    ),
                })
            observations.append({
                "time_s": env.physics.time(),
                "position_cm": data.xpos[body_id].tolist(),
                "motor_command": asdict(command),
                "observations": {
                    key: np.asarray(value).tolist() for key, value in timestep.observation.items()
                },
                "habitat": sample_habitat(model, data, body_id, habitat) if habitat is not None else None,
            })

        if headless:
            while len(control_records) < target_steps and not timestep.last():
                frame()
        else:
            print(
                f"Flight controller: {controller} (NOT connectome-driven). "
                "P/Space pause, X neutral. Raw W/S/A/D controls are "
                f"{'enabled' if controller == 'diagnostic' or allow_wing_overrides else 'disabled'}. "
                f"Starts {'paused' if paused else 'running'}.",
                flush=True,
            )
            state_guard = ViewerStateGuard(model, data)
            with managed_viewer(
                model, data, key_callback=commands.put,
                show_left_ui=False, show_right_ui=False,
            ) as viewer:
                viewer.cam.type = mj.mjtCamera.mjCAMERA_TRACKING
                viewer.cam.trackbodyid = body_id
                viewer.cam.lookat[:] = data.xpos[body_id]
                viewer.cam.distance = (
                    FLIGHT_UNITS.length_from_mm(habitat.half_size_mm)
                    if habitat is not None else 0.6
                )
                if habitat is not None:
                    viewer.cam.elevation = -35
                holding = False
                while viewer.is_running() and not close_requested:
                    finished = len(control_records) >= target_steps or timestep.last()
                    if finished and exit_on_complete:
                        break
                    if finished and not holding:
                        holding = True
                        (output / "status.json").write_text(json.dumps({
                            "status": "awaiting_viewer_close",
                            "completed_control_steps": len(control_records),
                            "requested_control_steps": target_steps,
                            "task_terminated": bool(timestep.last()),
                        }) + "\n")
                        print("Flight interval ended; viewer stays open for inspection. Press Q or close the window.", flush=True)
                    tick = time.perf_counter()
                    with viewer.lock():
                        state_guard.restore_if_changed()
                        frame()
                        state_guard.capture()
                        scene = viewer.user_scn
                        if scene is None:
                            raise RuntimeError("Viewer does not provide the required status scene")
                        scene.ngeom = 1
                        mj.mjv_initGeom(
                            scene.geoms[0], mj.mjtGeom.mjGEOM_LABEL,
                            np.zeros(3), data.xpos[body_id],
                            np.eye(3).ravel(), np.array([1.0, 1.0, 1.0, 1.0]),
                        )
                        finished = len(control_records) >= target_steps or timestep.last()
                        scene.geoms[0].label = viewer_status(
                            paused, env.physics.time(), seconds, finished,
                            len(control_records) < target_steps or boundary_exit_steps > 0,
                        )
                    viewer.sync()
                    time.sleep(max(0, 1 / 60 - (time.perf_counter() - tick)))
                with viewer.lock():
                    state_guard.restore_if_changed()
        finished = env.physics.time()
        summary = {
            "status": "completed" if len(control_records) == target_steps else (
                "episode_terminated" if timestep.last() else "closed_by_user"
            ),
            "upstream_commit": REVISION,
            "scope": (
                "Published trained reference-tracking policy, NOT connectome-driven."
                if policy is not None else
                "Uncontrolled wingbeat/aerodynamic diagnostic, NOT stable or brain-driven flight."
            ),
            "wingbeat_pattern": "Upstream wing_pattern_fmech.npy; no generated fallback",
            "reference": (
                f"Upstream flight trajectory {trajectory}; includes privileged future-reference observations"
                if reference == "measured" else
                "Explicit synthetic speed/heading/height goal; NOT extended measured data"
            ),
            "reference_mode": reference,
            "goal": {
                "speed_cm_s": speed_cm_s, "height_cm": height_cm, "yaw_rate_rad_s": yaw_rate_rad_s,
            } if reference == "straight-goal" else None,
            "simulated_seconds": finished, "requested_simulated_seconds": seconds,
            "available_reference_seconds": reference_seconds,
            "termination_reason": (
                "requested_duration" if len(control_records) == target_steps else
                "reference_complete" if env.task._reached_traj_end else
                "fatal_task_termination" if timestep.last() else "closed_by_user"
            ),
            "wall_seconds": time.perf_counter() - started,
            "physics_units": "centimeter, gram, second; gravity 981 cm/s^2",
            "initial_position_cm": initial.tolist(),
            "final_position_cm": data.xpos[body_id].tolist(),
            "initial_position_mm": [FLIGHT_UNITS.length_to_mm(value) for value in initial],
            "final_position_mm": [FLIGHT_UNITS.length_to_mm(value) for value in data.xpos[body_id]],
            "initial_wing_phase_index": initial_wing_phase_index,
            "initial_orientation_wxyz": initial_orientation.tolist(),
            "final_orientation_wxyz": data.xquat[body_id].tolist(),
            "final_body_z_dot_world_z": float(data.xmat[body_id].reshape(3, 3)[2, 2]),
            "stable_flight_validated": False,
            "reference_tracking_validated": False,
            "controller": controller, "seed": seed, "trajectory": trajectory,
            "tracking_validation": evaluate_tracking(control_records, finished, seconds),
            "clipped_policy_components": clipped_policy_components,
            "policy_wall_seconds": policy_wall_seconds,
            "physics_wall_seconds": physics_wall_seconds,
            "gust": {"lateral_force_uN": gust_uN, "start_s": gust_at_s, "duration_s": gust_duration_s},
            "physics_timestep_s": float(model.opt.timestep),
            "control_timestep_s": env.control_timestep(),
            "requested_control_steps": target_steps, "completed_control_steps": len(control_records),
            "wingbeat_base_frequency_Hz": float(env.task._wbpg.base_beat_freq),
            "fluid_density_g_cm3": float(model.opt.density),
            "aerodynamic_geoms": int(np.count_nonzero(model.geom_fluid[:, 0] > 0)),
            "motor_action_names": names, "events": events,
            "native_physics_edits_rejected": state_guard.rejections if state_guard is not None else 0,
            "raw_wing_overrides_enabled": controller == "diagnostic" or allow_wing_overrides,
            "exit_on_complete": exit_on_complete,
            "habitat": environment_dict(habitat) if habitat is not None else None,
            "habitat_sha256": hashlib.sha256(scene_path.read_bytes()).hexdigest() if scene_path else None,
            "habitat_module_sha256": hashlib.sha256((ROOT / "scripts/fly_flight_arena.py").read_bytes()).hexdigest(),
            "habitat_boundary_exit_steps": boundary_exit_steps,
            "first_habitat_boundary_exit_s": first_boundary_exit_s,
            "habitat_contact_steps": sum(record["arena_contacts"] > 0 for record in control_records),
            "habitat_navigation_validated": False,
            "habitat_sensors_drive_policy": False,
            "mujoco": importlib.metadata.version("mujoco"),
            "dm_control": importlib.metadata.version("dm-control"),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "dataset_checksum": "md5:bb35ce27e07c4ffbd3d56ff6dec90905",
            "policy_checksum": "md5:12934d5a1c60631a710bc2b6d297d3ce" if policy is not None else None,
            "policy_runtime": "tflite_mean_action" if policy is not None else None,
            "policy_artifact_sha256": policy.model_sha256 if policy is not None else None,
            "policy_module_sha256": hashlib.sha256((ROOT / "scripts/fly_policy.py").read_bytes()).hexdigest(),
            "unit_module_sha256": hashlib.sha256((ROOT / "scripts/sim_units.py").read_bytes()).hexdigest(),
        }
        if policy is not None:
            summary["tensorflow"] = importlib.metadata.version("tensorflow-cpu")
            summary["reference_tracking_validated"] = (
                seconds >= 0.5 and summary["tracking_validation"]["passed"]
            )
            if summary["status"] == "completed" and not summary["tracking_validation"]["passed"]:
                summary["status"] = "tracking_failed"
        if habitat is not None and summary["status"] == "completed" and boundary_exit_steps:
            summary["status"] = "habitat_boundary_exit"
        from PIL import Image
        with mj.Renderer(model, height=480, width=640) as renderer:
            camera = mj.MjvCamera()
            camera.type = mj.mjtCamera.mjCAMERA_FREE
            camera.lookat[:] = data.xpos[body_id]
            camera.distance = (
                FLIGHT_UNITS.length_from_mm(habitat.half_size_mm)
                if habitat is not None else 0.6
            )
            camera.elevation = -35 if habitat is not None else -25
            renderer.update_scene(data, camera)
            Image.fromarray(renderer.render()).save(output / "preview.png")
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        with (output / "observations.jsonl").open("w") as stream:
            for observation in observations:
                stream.write(json.dumps(observation, allow_nan=False) + "\n")
        with (output / "control_steps.jsonl").open("w") as stream:
            for record in control_records:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
        (output / "status.json").write_text(json.dumps({"status": summary["status"]}) + "\n")
        print(json.dumps(summary, indent=2))
        return summary["status"]
    except Exception as error:
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": str(error)}) + "\n")
        raise
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=0.05)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--start-paused", action="store_true", help="Inspect and set commands before beginning interactive diagnostic")
    parser.add_argument("--controller", choices=["diagnostic", "trained"], default="diagnostic")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trajectory", type=int, default=0)
    parser.add_argument("--gust-uN", type=float, default=0, help="Explicit lateral force perturbation, not calibrated airflow")
    parser.add_argument("--gust-at-s", type=float, default=0.2)
    parser.add_argument("--gust-duration-s", type=float, default=0.05)
    parser.add_argument("--reference", choices=["measured", "straight-goal"], default="measured")
    parser.add_argument("--speed-cm-s", type=float, default=20)
    parser.add_argument("--height-cm", type=float, default=1)
    parser.add_argument("--yaw-rate-rad-s", type=float, default=0)
    parser.add_argument("--allow-wing-overrides", action="store_true", help="Experimental raw wing controls can destabilize trained flight")
    parser.add_argument("--scene", type=Path, help="Shared walking habitat JSON; requires straight-goal mode")
    parser.add_argument("--exit-on-complete", action="store_true", help="Close native viewer at end of bounded flight; otherwise keep result visible")
    args = parser.parse_args()
    try:
        status = run(
            args.data_dir, args.output_dir, args.seconds, args.headless,
            args.start_paused, args.controller, args.seed, args.trajectory,
            args.gust_uN, args.gust_at_s, args.gust_duration_s,
            args.reference, args.speed_cm_s, args.height_cm, args.yaw_rate_rad_s,
            args.allow_wing_overrides,
            args.scene,
            args.exit_on_complete,
        )
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if status == "episode_terminated":
        print("ERROR: flight task terminated before requested duration; inspect diagnostic results", file=sys.stderr)
        return 2
    if status == "tracking_failed":
        print("ERROR: trained controller exceeded configured tracking thresholds; inspect results", file=sys.stderr)
        return 3
    if status == "habitat_boundary_exit":
        print("ERROR: flight goal left the configured habitat XY bounds; inspect or explicitly edit the scene/goal", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
