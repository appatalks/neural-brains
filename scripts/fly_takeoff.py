"""Experimental GF-triggered, motor-assisted physical takeoff and learned flight."""

import argparse
import hashlib
import json
import math
import queue
import sys
import time
from dataclasses import replace
from pathlib import Path

from datasets import ROOT, CATALOG
from fly_environment import Environment, environment_dict
from fly_feeding import BrainClient
from fly_finger import Looming, Pointer, pointer_target
from fly_flight import prepare_data
from fly_flight_arena import make_arena
from fly_policy import PublishedFlightPolicy, prepare_tflite_policy
from sim_units import FLIGHT_UNITS, simulation_steps
from sim_viewer import managed_viewer
from fly_graphics import ObserverScene


def launch_state(gf_spikes: dict, elapsed: float | None):
    if any(type(value) is not int or value < 0 for value in gf_spikes.values()):
        raise ValueError("Invalid giant-fiber spike counts")
    if elapsed is None:
        return "launch" if sum(gf_spikes.values()) > 0 else "grounded"
    return "launch" if elapsed < 0.3 else "flight"


def assisted_force(mass_g, position, velocity, rotation, desired_rotation, target, target_velocity=None):
    import numpy as np
    if not math.isfinite(mass_g) or mass_g <= 0:
        raise ValueError("Body mass must be finite and positive")
    desired_velocity = [20,0,0] if target_velocity is None else target_velocity
    if len(desired_velocity)!=3 or any(not math.isfinite(v) for v in desired_velocity):
        raise ValueError("Launch target velocity must be a finite world-space vector")
    force = mass_g * (
        3000 * (target - position) - 100 * (velocity[3:] - desired_velocity) + [0, 0, 981]
    )
    force = np.clip(force, -4 * mass_g * 981, 4 * mass_g * 981)
    error = sum(np.cross(rotation[:, i], desired_rotation[:, i]) for i in range(3)) * 0.5
    torque = mass_g * 0.02 * (800 * error - 50 * velocity[:3])
    return np.concatenate([force, torque])


def create_environment(paths, habitat, seconds):
    import numpy as np
    from dm_control import composer
    from flybody.fruitfly.fruitfly import FruitFly
    from flybody.tasks.flight_imitation import FlightImitationWBPG
    from flybody.tasks.pattern_generators import WingBeatPatternGenerator
    from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
    from flybody.tasks.trajectory_loaders import InferenceFlightTrajectoryLoader

    dt = 0.0002
    total = simulation_steps(seconds, dt) + 6
    qpos, qvel = constant_speed_trajectory(
        n_steps=total, speed=20, init_pos=(0, 0, 1),
        body_rot_angle_y=-47.5, control_timestep=dt,
    )
    loader = InferenceFlightTrajectoryLoader()
    loader.set_next_trajectory(qpos, qvel)

    class HybridTask(FlightImitationWBPG):
        def initialize_episode(self, physics, random_state):
            super().initialize_episode(physics, random_state)
            self.launch_time = None
            self.launch_origin = None
            pos, quat = self.walker.get_pose(physics)
            position = np.asarray(pos).copy()
            position[2] = 0.15
            self.walker.set_pose(physics, position, np.asarray(quat).copy())
            physics.data.qvel[:] = 0
            self._should_terminate = False

        def begin_launch(self, physics):
            self.launch_time = physics.time()
            position, _ = self.walker.get_pose(physics)
            self.launch_origin = np.asarray(position).copy()
            # Only desired reference positions change; body state is not assigned.
            times = np.maximum(0, np.arange(len(self._ref_qpos)) * dt - self.launch_time)
            self._ref_qpos[:, 0] = self.launch_origin[0] + 20 * times
            self._ref_qpos[:, 1] = self.launch_origin[1]
            self._ref_qpos[:, 2] = 1.0

        def before_step(self, physics, action, random_state):
            if self.launch_time is None:
                self._step_counter += 1
                self.walker.apply_action(physics, np.zeros_like(action), random_state)
            else:
                super().before_step(physics, action, random_state)

        def check_termination(self, physics):
            if self.launch_time is None or physics.time() - self.launch_time < 0.35:
                return False
            return super().check_termination(physics)

        def get_reward(self, physics):
            if self.launch_time is None:
                self._should_terminate = False
                return 0.0
            return super().get_reward(physics)

    arena = make_arena(habitat)
    finger = arena.mjcf_model.worldbody.add("body", name="virtual_finger", mocap=True, pos=[0, 0, -10])
    finger.add("geom", name="finger_tip", type="sphere", size=[0.15], rgba=[0.85, 0.55, 0.4, 1])
    finger.add("geom", name="finger_shaft", type="capsule", fromto=[0, 0, 0.05, 0, 0, 0.5],
               size=[0.11], rgba=[0.78, 0.48, 0.34, 1], contype=0, conaffinity=0)
    task = HybridTask(
        walker=FruitFly, arena=arena,
        wbpg=WingBeatPatternGenerator(base_pattern_path=str(paths["wing_pattern_fmech.npy"])),
        traj_generator=loader, time_limit=total * dt, terminal_com_dist=2,
        initialize_qvel=False, force_actuators=False, disable_legs=True,
        joint_filter=0, future_steps=5, floor_contacts=True,
    )
    return composer.Environment(
        time_limit=total * dt, task=task, random_state=np.random.RandomState(0),
        strip_singleton_obs_buffer_dim=True,
    )


def run(data_dir, output, seconds, headless, test_approach, arena_half_size, exit_on_complete=False):
    import mujoco as mj
    import numpy as np

    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        raise ValueError("Choose a new external result directory")
    if not math.isfinite(seconds) or not 0.5 <= seconds <= 60:
        raise ValueError("Duration must be between 0.5 and 60 seconds")
    if not math.isfinite(arena_half_size) or arena_half_size < 30:
        raise ValueError("Arena half size must be at least 30 mm")
    steps = simulation_steps(seconds, 0.0002)
    habitat = Environment.load(ROOT / "experiments/fly-walking/habitat.json")
    habitat = replace(habitat, half_size_mm=arena_half_size)
    env = create_environment(prepare_data(data_dir), habitat, seconds)
    output.mkdir(parents=True)
    (output / "environment.json").write_text(json.dumps(environment_dict(habitat), indent=2) + "\n")
    (output / "status.json").write_text('{"status": "loading"}\n')
    brain = None
    records = (output / "takeoff.jsonl").open("x")
    commands = queue.SimpleQueue()
    paused = False
    hand_enabled = False
    hand_target = np.array([2., 0., 0.15])
    hand_position = hand_target.copy()
    looming = Looming()
    ticks = 0
    phase = "grounded"
    triggered_at = None
    maximum_height = 0
    post_launch_samples = []
    initial_contact = False
    maximum_post_assistance_floor_contacts = 0
    boundary_exit_steps = 0
    model_state_hash = None
    started = time.perf_counter()
    try:
        timestep = env.reset()
        model, data = env.physics.model.ptr, env.physics.data.ptr
        ground = mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, "groundplane")
        if ground < 0:
            raise ValueError("Physical ground plane missing")
        if model.geom_contype[ground] == 0 or model.geom_conaffinity[ground] == 0:
            raise ValueError("Ground contact must be enabled before model compilation")
        body = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, "walker/thorax")
        finger_body = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, "virtual_finger")
        finger_mocap = model.body_mocapid[finger_body]
        if min(body, finger_mocap) < 0:
            raise ValueError("Required physical bodies missing")
        initial_position = data.xpos[body].copy()
        desired_rotation = data.xmat[body].reshape(3, 3).copy()
        mass = sum(model.body_mass[i] for i in range(model.nbody)
                   if (mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i) or "").startswith("walker"))
        policy = PublishedFlightPolicy(prepare_tflite_policy(data_dir, CATALOG))
        brain = BrainClient(ROOT / ".venv/bin/python", data_dir, output, 420, takeoff=True)
        (output / "brain-metadata.json").write_text(json.dumps(brain.metadata, indent=2) + "\n")
        model_state_hash = hashlib.sha256(model.body_mass.tobytes() + model.body_inertia.tobytes()).hexdigest()
        (output / "status.json").write_text('{"status": "running"}\n')
        viewer = None
        pointer = None
        pointer_scene = mj.MjvScene(model, maxgeom=10000)

        def interval():
            nonlocal ticks, phase, timestep, triggered_at, maximum_height, initial_contact, paused, hand_enabled
            nonlocal maximum_post_assistance_floor_contacts, boundary_exit_steps
            while not commands.empty():
                code = commands.get()
                if code == ord("Q"):
                    return False
                if code in [ord("P"), 32]:
                    paused = not paused
                if code == ord("H"):
                    hand_enabled = not hand_enabled
            if paused:
                return True
            timestamp = ticks * 0.0002
            if test_approach:
                hand_enabled = 0.12 <= timestamp < 0.35
                hand_target[:] = [max(0.4, 2 - 8 * max(0, timestamp - 0.12)), 0, 0.5]
            if viewer is not None and hand_enabled and not test_approach:
                # Older MuJoCo flight viewer lacks Handle.viewport; use the
                # explicit X11 window rectangle for this backend.
                viewport = pointer.window_viewport()
                cursor = pointer.position(viewport)
                if cursor is not None:
                    mj.mjv_updateScene(model, data, viewer.opt, None, viewer.cam, mj.mjtCatBit.mjCAT_ALL, pointer_scene)
                    camera = mj.mjv_averageCamera(pointer_scene.camera[0], pointer_scene.camera[1])
                    target = pointer_target(camera, viewport, *cursor, plane_z=0.5)
                    if target is not None:
                        hand_target[:] = target
            duration_steps = min(50, steps - ticks)
            delta = hand_target - hand_position
            norm = np.linalg.norm(delta)
            hand_position[:] += delta * min(1, 2 * duration_steps * 0.0002 / norm) if norm else 0
            data.mocap_pos[finger_mocap] = hand_position if hand_enabled else [0, 0, -10]
            mj.mj_forward(model, data)
            features = looming.sample(
                float(np.linalg.norm(hand_position - data.xpos[body])) * 10,
                1.5, duration_steps * 0.0002, hand_enabled,
            )
            brain.begin_step(duration_steps * 0.2, False, features["looming_active"])
            response = brain.finish_step()
            launch_pending = triggered_at is None and sum(response["giant_fiber_spikes"].values()) > 0
            for _ in range(duration_steps):
                timestamp = ticks * 0.0002
                elapsed = None if triggered_at is None else timestamp - triggered_at
                phase = launch_state({}, elapsed)
                action = np.zeros(env.action_spec().shape)
                if triggered_at is not None:
                    action, _ = policy.action(timestep.observation, env.action_spec())
                data.xfrc_applied[body] = 0
                assistance = np.zeros(6)
                if phase == "launch":
                    velocity = np.zeros(6)
                    mj.mj_objectVelocity(model, data, mj.mjtObj.mjOBJ_BODY, body, velocity, False)
                    target = np.array([env.task.launch_origin[0] + 20 * elapsed,
                                       env.task.launch_origin[1], 1])
                    assistance = assisted_force(mass, data.xpos[body], velocity,
                                                data.xmat[body].reshape(3, 3), desired_rotation, target)
                    data.xfrc_applied[body] = assistance
                timestep = env.step(action)
                ticks += 1
                if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                    raise RuntimeError("Nonfinite physical state")
                maximum_height = max(maximum_height, float(data.xpos[body, 2]))
                if phase == "grounded" and any(
                    c.geom1 == ground or c.geom2 == ground for c in data.contact[:data.ncon]
                ):
                    initial_contact = True
                if phase == "flight":
                    post_launch_samples.append(float(data.xpos[body, 2]))
                    floor_contacts = sum(
                        int(c.geom1 == ground or c.geom2 == ground)
                        for c in data.contact[:data.ncon]
                    )
                    maximum_post_assistance_floor_contacts = max(maximum_post_assistance_floor_contacts, floor_contacts)
                if any(abs(value * 10) > arena_half_size for value in data.xpos[body, :2]):
                    boundary_exit_steps += 1
                if timestep.last():
                    break
            if launch_pending and not timestep.last():
                triggered_at = ticks * 0.0002
                env.task.begin_launch(env.physics)
                phase = "launch"
            records.write(json.dumps({
                "time_s": ticks * 0.0002, "phase": phase,
                "position_cm": data.xpos[body].tolist(), "gf_response": response,
                "looming": features, "assistance_force_torque_cgs": assistance.tolist(),
                "contacts": data.ncon,
                "launch_trigger_deferred_to_interval_end": launch_pending,
                "neural_clock_ms": response["brain_time_ms"],
                "body_velocity": data.qvel[:6].tolist(),
            }, allow_nan=False) + "\n")
            records.flush()
            return not timestep.last()

        if headless:
            while ticks < steps and interval():
                pass
        else:
            observer = ObserverScene(model, data)
            with managed_viewer(observer.model, observer.data, key_callback=commands.put,
                                show_left_ui=False, show_right_ui=False) as viewer:
                pointer = Pointer()
                viewer.cam.lookat[:] = initial_position
                viewer.cam.type = mj.mjtCamera.mjCAMERA_TRACKING
                viewer.cam.trackbodyid = body
                viewer.cam.distance = min(5, arena_half_size / 10)
                viewer.cam.elevation = -25
                while viewer.is_running() and ticks < steps:
                    with viewer.lock():
                        ongoing = interval()
                        observer.sync()
                        scene = viewer.user_scn
                        scene.ngeom = 1
                        mj.mjv_initGeom(scene.geoms[0], mj.mjtGeom.mjGEOM_LABEL, np.zeros(3),
                                        data.xpos[body], np.eye(3).ravel(), np.ones(4))
                        scene.geoms[0].label = f"HYBRID {phase}: H finger / P pause / Q close"
                    viewer.sync()
                    if not ongoing:
                        break
                    time.sleep(0.001)
                if not exit_on_complete:
                    (output / "status.json").write_text('{"status": "awaiting_viewer_close"}\n')
                    while viewer.is_running():
                        close = False
                        while not commands.empty():
                            if commands.get() == ord("Q"):
                                close = True
                        if close:
                            break
                        with viewer.lock():
                            viewer.user_scn.geoms[0].label = "HYBRID interval ended: Q saves/closes"
                        viewer.sync()
                        time.sleep(0.02)
        successful = (
            ticks == steps and triggered_at is not None and initial_contact
            and len(post_launch_samples) >= 2500
            and min(post_launch_samples[-2500:]) > 0.5
            and maximum_post_assistance_floor_contacts == 0
            and boundary_exit_steps == 0
        )
        summary = {
            "status": "completed" if ticks == steps else "stopped",
            "experimental_hybrid": True, "biological_motor_decoding": False,
            "neural_trigger": "actual GF spike count >0; engineering threshold",
            "neural_trigger_time_s": triggered_at, "ground_contact_observed": initial_contact,
            "initial_position_cm": initial_position.tolist(), "final_position_cm": data.xpos[body].tolist(),
            "maximum_height_cm": maximum_height, "post_assistance_flight_steps": len(post_launch_samples),
            "sustained_flight_check_passed": successful,
            "criterion": "Observed initial floor contact; >=0.5s after assistance with height>0.5cm, no floor contact or arena exit; engineering test",
            "post_assistance_max_floor_contacts": maximum_post_assistance_floor_contacts,
            "arena_boundary_exit_steps": boundary_exit_steps,
            "assistance_duration_s": 0.3, "gravity_cm_s2": model.opt.gravity.tolist(),
            "same_body_no_runtime_pose_reset": True, "simulated_seconds": ticks * 0.0002,
            "body_mass_g": mass, "body_mass_inertia_sha256": model_state_hash,
            "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_model_revision": "d015e9bfe441bd90ae431bac24c55cb74bdbce26",
            "motor_assistance": {
                "translational_gain_s2": 3000, "velocity_gain_s": 100,
                "orientation_gain": 800, "angular_velocity_gain": 50,
                "torque_scale_mass_cm2": 0.02, "maximum_force_per_axis_weights": 4,
                "physiological_muscle_model": False,
            },
            "wall_seconds": time.perf_counter() - started,
            "arena_half_size_mm": arena_half_size,
            "limitations": [
                "Learned wing policy and external force/torque assistance replace unknown motor decoding.",
                "Flight body has retracted legs; no neural walking controller.",
                "Looming gate is uncalibrated; controller consumes synthetic future-reference goals.",
                "No physiological jump muscle model, landing, or proven universal stability.",
            ],
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        from PIL import Image
        observer = ObserverScene(model, data)
        with mj.Renderer(observer.model, height=480, width=640) as renderer:
            camera = mj.MjvCamera()
            camera.lookat[:] = data.xpos[body]
            camera.distance = 0.8
            camera.elevation = -25
            renderer.update_scene(observer.data, camera)
            Image.fromarray(renderer.render()).save(output / "preview.png")
        (output / "status.json").write_text(json.dumps({"status": summary["status"]}) + "\n")
        print(json.dumps(summary, indent=2))
        return successful if test_approach else True
    except Exception as error:
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": str(error)}) + "\n")
        raise
    finally:
        records.close()
        if brain:
            brain.close()
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=2)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--test-approach", action="store_true", help="Explicit repeatable approaching-finger test stimulus")
    parser.add_argument("--arena-half-size-mm", type=float, default=30, help="Explicit arena size; fast flight needs more than the original 30 mm half-size")
    parser.add_argument("--exit-on-complete", action="store_true", help="Close viewer at interval end; default retains final result for inspection")
    args = parser.parse_args()
    try:
        passed = run(args.data_dir, args.output_dir, args.seconds, args.headless,
                     args.test_approach, args.arena_half_size_mm, args.exit_on_complete)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        print(f"ERROR: hybrid takeoff failed: {error}", file=sys.stderr)
        return 1
    if not passed:
        print("ERROR: physical launch/flight check did not pass; inspect summary", file=sys.stderr)
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
