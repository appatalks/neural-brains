"""Main environment-only habitat; automatic hybrid behavior, no manual modes."""

import argparse
import sys
import subprocess
from pathlib import Path

from datasets import ROOT
from fly_walking import run
from fly_dashboard import DEFAULT_PORT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="External FlyWire input and result root")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scene", type=Path, help="Shared environment; unified defaults to grassland, walking retains its legacy scene")
    parser.add_argument("--feeding-config", type=Path,
                        help="Explicit food exposure/readout configuration matched to the scene")
    parser.add_argument("--seconds", type=float, help="Bounded experiment; omit for ongoing interactive habitat")
    parser.add_argument("--headless", action="store_true", help="Requires a bounded duration")
    parser.add_argument("--schedule", type=Path, help="Environment intervention/restart schedule; no direct steering")
    parser.add_argument("--virtual-finger", action="store_true", help="Physical pointer object and live giant-fiber diagnostic; H enables finger")
    parser.add_argument("--objects", type=Path, help="Reload saved object placements (requires virtual-finger)")
    parser.add_argument("--neural-dashboard", action="store_true", help="Serve a loopback companion for eyes and interactive actual neuron activity")
    parser.add_argument("--native-window", action="store_true", help="Use the legacy separate native viewer instead of the single browser app")
    parser.add_argument("--dashboard-port", type=int, choices=[DEFAULT_PORT], default=DEFAULT_PORT,
                        help="Single browser-app port; alternate and ephemeral ports are disabled")
    parser.add_argument("--backend",choices=["walking","unified"],default="walking",
                        help="walking preserves the current habitat; unified explicitly selects experimental assisted flight")
    parser.add_argument("--flight-arena-half-size-mm",type=float,default=112.5,
                        help="Explicit arena half-size for the experimental unified backend")
    parser.add_argument("--neural-leg-extension",action="store_true",
                        help="Opt-in DNp10 reduced VNC/leg-actuator surrogate on the unified backend")
    parser.add_argument("--graded-vision",action="store_true",
                        help="Opt-in continuous sphere size/velocity encoding on the unified backend")
    parser.add_argument("--flight-avoidance",action="store_true",
                        help="Engineered predictive turning through learned wings on unified backend")
    parser.add_argument("--brain-linked-landing",action="store_true",
                        help="Actual DNp10 initiated assumed assisted landing; includes engineered walking-boundary reference")
    parser.add_argument("--landing-surface-vision",action="store_true",
                        help="Explicit approximate surface-expansion input for brain-linked landing")
    args = parser.parse_args(argv)
    if args.scene is None:
        args.scene = ROOT/"experiments/fly-walking"/("grassland-habitat.json" if args.backend=="unified" else "habitat.json")
    if args.feeding_config is None:
        filename = "grassland-feeding.json" if args.backend=="unified" and args.scene.resolve()==ROOT/"experiments/fly-walking/grassland-habitat.json" else "live-feeding.json"
        args.feeding_config = ROOT/"experiments/flywire-sugar"/filename
    if args.headless and args.seconds is None:
        parser.error("--headless requires --seconds")
    if args.neural_leg_extension and args.backend != "unified":
        parser.error("--neural-leg-extension requires --backend unified")
    if args.graded_vision and args.backend != "unified":
        parser.error("--graded-vision requires --backend unified")
    if args.flight_avoidance and args.backend != "unified":
        parser.error("--flight-avoidance requires --backend unified")
    if (args.brain_linked_landing or args.landing_surface_vision) and args.backend!="unified":
        parser.error("Brain-linked landing requires --backend unified")
    if args.backend=="unified":
        if args.native_window or args.schedule:
            parser.error("Unified browser backend does not support native-window or schedules")
        command=[
            str(ROOT/".venv-flight/bin/python"),str(ROOT/"scripts/fly_flight_app.py"),
            "--data-dir",str(args.data_dir),"--output-dir",str(args.output_dir),
            "--scene",str(args.scene),"--feeding-config",str(args.feeding_config),
            "--dashboard-port",str(args.dashboard_port),
            "--arena-half-size-mm",str(args.flight_arena_half_size_mm),
        ]
        if args.seconds is not None:
            command.extend(["--seconds",str(args.seconds)])
        if args.objects:
            command.extend(["--objects",str(args.objects)])
        if args.neural_leg_extension:
            command.append("--neural-leg-extension")
        if args.graded_vision:
            command.append("--graded-vision")
        if args.flight_avoidance:
            command.append("--flight-avoidance")
        if args.brain_linked_landing:
            command.append("--brain-linked-landing")
        if args.landing_surface_vision:
            command.append("--landing-surface-vision")
        return subprocess.run(command,check=False).returncode
    try:
        run(
            output=args.output_dir, seconds=args.seconds if args.seconds is not None else 60,
            headless=args.headless, scene=args.scene, schedule_path=args.schedule,
            sensory=True, until_closed=args.seconds is None, vision=True,
            self_righting=True,
            brain_feeding=args.feeding_config,
            brain_data_dir=args.data_dir, autonomous=True,
            observer_graphics=True,
            virtual_finger=args.virtual_finger,
            objects_path=args.objects,
            neural_dashboard=args.neural_dashboard or not (args.native_window or args.headless),
            dashboard_port=args.dashboard_port,
            browser_app=not (args.native_window or args.headless),
        )
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        print(f"ERROR: autonomous habitat failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
