# Interactive biomechanical fly walking

This is an interactive 3D **NeuroMechFly/FlyGym** body simulation in MuJoCo,
with the upstream hybrid central-pattern-generator/reflex walking controller.
It is **not controlled by the FlyWire brain model**, and it is not a
validated simulation of arbitrary real fly behavior.

There is now an optional [live FlyWire feeding bridge](../flywire-sugar/LIVE.md).
It runs actual brain spikes from geometric sugar exposure and shows MN9
activity; it does not control this walking controller or physical proboscis.
`--brain-feeding` and `--brain-data-dir` enable it together. T toggles sugar.
The normal habitat remains available without a neural worker.

It now supports configurable physical habitats, logged sensory observations,
an explicit walking motor-command contract, and reproducible timed
perturbations. The sensory-demo policy is an engineered baseline, not a brain.

The user selected biomechanical walking and terrain interaction before
connectome-to-body coupling. We reuse the anatomical body and published
controller instead of inventing an avatar and labeling its animation neural.

## Start the viewer

The main user-facing habitat now uses a mode-free launcher:

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/autonomous-session-001"
```

It automatically enables the preserved habitat, rendered visual input,
engineered environment-response walking, experimental leg-only recovery,
and actual FlyWire feeding spikes. There is no user-selected locomotion
mode. The overlay identifies the hybrid architecture; neural feeding still
does not supply walking or physical proboscis actuation.

Only environmental/session actions remain: sugar, terrain, friction, force,
pause, explicit restart, camera, playback speed, and close. Manual
steering/controller-switch keys are ignored with explicit warnings and
logged events. The brain/circuit is not changed by choosing a mode.

`fly_habitat.py --headless --seconds 0.8` provides a bounded validation run;
headless operation requires an explicit duration. Original lower-level
launch commands below remain research baselines, not the main experience.
Their existing behavior is preserved for scientific comparison.

For an ongoing habitat session, use `--until-closed`:

```bash
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --until-closed --scene experiments/fly-walking/habitat.json \
  --controller sensory-demo \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/habitat-session-001"
```

This keeps simulating until **Q** or window close. Pausing, resetting the fly,
turning, terrain/friction changes, and sensor mode switching remain available.
Trajectory and sensory records are streamed to external disk rather than
accumulated in memory; long sessions still consume disk space. Close normally
to save the final event log and summary. This is not an auto-repeating flight
test or a walking-to-flight transition.

Bounded runs with `--seconds` retain their existing behavior; headless runs
cannot use `--until-closed`. In persistent mode the finite `--seconds` value
is ignored, and no maximum simulated step count is recorded.

The persistent-session viewer was tested beyond its former 0.5-second
limit: it kept advancing, accepted pause/terrain/friction/controller/reset
commands, and saved the session normally on Q. Bounded-mode trajectory and
sensory logs remained byte-identical after switching to streamed logging.

The first persistent-session test saved its scientific results but reported
`GLXBadContext` during process teardown. The native viewer's close method
only requests render-thread shutdown; exiting Python could race OpenGL
cleanup. Both backends now use [managed viewer shutdown](../../scripts/sim_viewer.py)
to wait for the newly created native render thread. A subsequent native
walking test exited with code 0, without that GLX teardown error.

Run these commands from the repository root. Set `FLY_DATA_DIR` to your
external data directory. The existing selected location is on the mounted
XFS volume.

```bash
uv venv --python /usr/bin/python3 .venv-biomechanics
uv pip install --python .venv-biomechanics/bin/python \
  -r experiments/fly-walking/requirements.lock.txt

export FLYGYM_ASSET_CACHE_DIR="$FLY_DATA_DIR/flygym-assets"
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --seconds 60 \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/interactive-001"
```

The Python interpreter must be **3.12–3.14**. `/usr/bin/python3` is 3.13.5
on the tested machine; use a suitable explicit interpreter elsewhere.
Do not install these dependencies in the Brian 2 `.venv`: FlyGym uses
NumPy 2 and MuJoCo 3.9, whereas the neural reproduction uses Python 3.10
and NumPy 1.

Use a new output directory on each run. The viewer needs a working display
and OpenGL. Do not set headless EGL variables for the native viewer unless
your rendering configuration requires them.

## Controls

The manual W/S/A/D/X/N keys in the table below apply only to the lower-level
research script. They are absent from the main autonomous launcher.

The camera now starts in **free** mode. Hold right mouse to pan and use the
other native mouse controls for orbit/zoom. **C** explicitly enables/disables
fly-follow mode; tracking mode overrides free panning because it recenters
on the fly. The habitat view starts wider so the walls and terrain remain
visible.

Click/focus **this simulation's MuJoCo window** before pressing keys. Do not
send commands to other MuJoCo windows that may already be open.

| Input | Effect |
| --- | --- |
| W / S | Increase/decrease the controller's drive command |
| A / D | Adjust differential turning command |
| X | Return turning command to zero |
| P | Pause/resume this simulation loop |
| O | Toggle three low terrain bars on/off |
| F | Toggle the ground's sliding friction between original and 0.1 |
| B | Apply a 5 microNewton lateral thorax force for 50 ms of simulated time |
| R | Reset fly physics and controller to their initial state |
| N | Toggle manual drive / engineered sensory-demo policy |
| Q | Save and close the session |
| C | Toggle free camera / fly tracking (free is the default) |
| [ / ] | Request slower/faster playback pacing |
| Mouse drag / wheel | Rotate, pan, or zoom using native viewer controls |
| B (application perturbation) | Logged lateral force; native physics editing is now guarded |
| Close window | End the run and save its summary |

Controller commands are explicitly user-supplied, not simulated perception
or autonomous decision-making. Turning direction and response should be
observed rather than interpreted as a validated animal response.
The controller uses joint position actuators and adhesion, not a complete
physiological muscle activation model.

The three bars are at x = 5, 10, and 15 mm, each 0.3 mm high. They are
registered as ground-contact geometry for fly/terrain physics. Toggling them
moves them below the plane; it does not generate a new learned terrain policy.
Low friction changes the ground plane only, not the bars.

The application owns physics state; native simulation panels are now hidden
and state edits are rejected to prevent controller/neural desynchronization.
Free camera controls remain available. Use application keys for reset,
pause, and force; native Ctrl-drag physics perturbations are not supported.
Camera movement is not recorded in the replay log.

## Live interaction versus real-time physics

The viewer displays the **live physical state**, not a prerecorded video.
However, the tested CPU/controller path runs approximately **0.30 times
real time**: a simulated second takes around 3.3 wall-clock seconds.
The display updates as the model advances and the overlay shows measured
throughput.

Playback controls can slow pacing but cannot accelerate computation beyond
hardware/controller throughput. GPU simulation is **not enabled** in this
first implementation, even though the machine has a compatible NVIDIA GPU.
Do not advertise real-time physical speed until a measured run meets it.

## Headless validation

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_walking.py \
  --headless --seconds 2 \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/physics-001"
```

This writes a rendered `preview.png` along with summary and trajectory.
EGL needs a supported rendering configuration; an unavailable renderer
produces an explicit error, not a placeholder image.

Measured checks on 2026-10-10:

- 2 simulated seconds completed in about **6.46 wall-clock seconds**.
- Model contained **69 bodies and 48 actuators**.
- Forward displacement was approximately **26.19 mm**, with finite states.
- The repeat headless run reproduced the same final position.
- The native viewer opened and displayed the live fly.
- Keyboard pause/resume, obstacle toggle, friction toggle, lateral push,
  and differential drive generated six recorded events in an 8-second
  interactive test.
- A subsequent isolated native viewer run completed with exit code 0.
  The earlier automated interaction run wrote completed results but its
  tool session reported exit code 1; don't use file presence alone to infer
  clean process termination.
- Rendered anatomy/terrain preview was visually inspected.
- Offline tests cover control bounds/toggles and output-directory protection.

These checks establish that the software functions, not new biological
validation of the body/controller.

## Rendered eye and retina observations

The eye inset is now anchored to the **top-right of the scene viewport**
and resized to fit smaller viewports.

```bash
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --until-closed --vision --scene experiments/fly-walking/habitat.json \
  --controller sensory-demo \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/vision-session-001"
```

`--vision` adds FlyGym's supported left/right eye cameras, fisheye correction,
and ommatidial channel mapping. Actual eye images appear as an inset in the
viewer. The final images are saved as `eyes.png`; `vision.jsonl` records
retinal channel arrays at about 10 Hz of simulated time.

This is not a visually controlled connectome. With `--vision` and
`--controller sensory-demo`, normalized left/right retinal channel intensity
now contributes to steering, alongside proximity rays and odor proxies.
This is an engineered intensity-attraction policy, not biological motion/
optic-flow circuitry or FlyWire visual processing. Vision rendering adds cost and two model camera
bodies; it is optional so original model-only runs remain available.

Following hands-on wall-contact feedback, engineered avoidance now begins
at 5 mm forward clearance and considers very close side obstacles. It slows
the gait and turns toward the clearer side. Measured differential-drive
tests confirmed the turn direction before modifying the controller.
A 10-second no-vision habitat run stayed inside the arena with no fallen
observation frames (minimum body uprightness approximately 0.813).
This is one software benchmark, not a guarantee against all collisions.

Body uprightness is now recorded. In sensory-demo mode a fallen body
(uprightness below 0.25) receives zero gait drive and the viewer reports
that recovery is unavailable. **There is no autonomous self-righting**:
R remains an explicit user reset, not a biological recovery maneuver.
Manual mode can still issue gait commands while fallen.

### Experimental physical self-righting

Add `--self-righting` to opt into an engineered leg-actuator maneuver:

```bash
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --until-closed --vision --self-righting \
  --scene experiments/fly-walking/habitat.json --controller sensory-demo \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/perception-recovery-001"
```

Recovery detects a fallen pose, disables leg adhesion during a 0.3-second
asymmetric joint-target push, then hands back to the walking controller.
Success requires body uprightness >=0.8 for 0.5 continuous seconds; failure
times out after 2 seconds of stabilization and is logged with a warning.
It does not assign the body pose, rotate it directly, or invoke reset.
The normal R command is still an explicit user reset.

Joint offsets were selected by bounded deterministic searches, not measured
animal data. The first prototype failed when habitat wind was retained;
the selected prototype was evaluated with wind. These targets are tuned to
this model and habitat, not a validated general recovery controller.

Validation:

- Explicit 180-degree inverted initialization recovered with and without
  eye rendering; success occurred at about 0.813 simulated seconds.
- A perturbed 168.54-degree start failed and timed out. This failure remains
  recorded; general robustness is not solved.
- `--initial-roll-deg` is diagnostic initialization only, not a recovery trick.
- Full offsets, phases, attempt/success/failure counts and module hash are
  saved in results.

This supersedes the earlier statement that recovery is unavailable, but only
when the experimental option is enabled. Flight transitions remain separate
and no recovery/visual policy is connectome-driven.

Long-lived session code fingerprints are now captured when the script
loads, not when it closes. The first hands-on session predated this fix;
its final source hashes may reflect files edited while it was running,
so they are not a trustworthy execution snapshot for that old session.

## Provenance and outputs

- Framework: [FlyGym](https://github.com/NeLy-EPFL/flygym)
- Pinned revision: `38c8ec61034cd59bc5ba0de20688d4a3c0000d60`
- License reported by upstream: Apache-2.0; preserve upstream notices and
  review asset-specific terms before redistribution.
- Documentation: [NeuroMechFly](https://neuromechfly.org/)
- Body/controller context: [NeuroMechFly v2 paper](https://doi.org/10.1038/s41592-024-02497-y)
- Alternative walking/flight body framework evaluated:
  [TuragaLab/flybody](https://github.com/TuragaLab/flybody)

The pinned framework's default simplified meshes and controller assets
come with the installed package. Optional large meshes are lazily fetched
from EPFL's object store; set `FLYGYM_ASSET_CACHE_DIR` to keep such assets in
external storage. This application does not request the high-resolution or
FlyBody mesh set.

Each run writes `trajectory.csv`, `events.json`, `summary.json`, and
`status.json` in the external output directory. The summary identifies
framework/source revision, controller, timestep, displacement, throughput,
and current controls. Failed runs retain an explicit failure status.
No result files or body meshes are committed to Git.

The live viewer is intentionally native rather than browser-based. There
is no saved scene editor or obstacle-placement UI yet.

## Configurable habitat and sensory interfaces

The checked-in [habitat](habitat.json) specifies a 60 x 60 mm arena, 3 mm
walls, a low bar, tilted box ramp, block obstacle, per-surface friction,
odor/light sources, and wind:

```bash
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --scene experiments/fly-walking/habitat.json \
  --controller sensory-demo --seconds 60 \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/habitat-interactive-001"
```

Positions/half-sizes are in millimeters; pitch is radians. The loader rejects
unknown fields, non-finite numbers, duplicate names, and terrain beyond arena
bounds. The habitat enables body/leg contact geometry. Omitting `--scene`
preserves the original flat/bar layout and contact preset.
O hides configured terrain but does not remove arena walls; F changes the
ground plane's friction, not all terrain surfaces.

[fly_environment.py](../../scripts/fly_environment.py) defines:

- `Observation`: time/reset episode, thorax position/velocity, left/right
  odor/light channels, three proximity ranges, joint angles/velocities,
  and contact count.
- `MotorCommand`: bounded left/right walking drive in [0, 1.5].
  Unsupported locomotion modes fail explicitly.
- `sensory_command`: an engineered odor-gradient/obstacle-avoidance policy
  feeding the existing hybrid controller. Light is recorded but does not
  alter this policy.

High-level observations/commands are sampled at approximately 60 Hz of
simulated time. The CPG/reflex controller still receives mechanosensory
observations every 0.1 ms physics step. `sensors.jsonl` records each input
observation, chosen motor command, and wind force.

**Explicit approximations:** odor/light intensities are uncalibrated static
Gaussian fields, sampled at approximate head-relative offsets. They are not
advection/diffusion, receptor dynamics, or radiometry. Three raycasts provide
engineered proximity, not compound-eye vision. Wind uses capped linear drag
on the thorax, not CFD or wing aerodynamics. Drive values are not descending
neuron firing rates. These limitations also appear in each run summary.

### Replayable interventions

The [example schedule](perturbations.json) applies a push, friction change,
terrain removal, turn, and straightening:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_walking.py \
  --headless --seconds 1.2 \
  --scene experiments/fly-walking/habitat.json \
  --schedule experiments/fly-walking/perturbations.json \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/habitat-001"
```

Sorted entries contain `time_s` and `key`. Each executes at the first frame
boundary at/after that simulated time, with about 16.7 ms timing resolution.
Events beyond the run duration are rejected. Pause is interactive-only:
a simulated-time schedule cannot advance while paused.

Environment/schedule snapshots and hashes are saved alongside the
runner/environment-module hashes. Resets increment an episode counter;
elapsed experiment time remains monotonic.

Validation:

- All five scheduled interventions executed.
- A complete repeat matched events, trajectory, and sensory/motor logs
  byte-for-byte.
- Moving a real test wall away changed forward range from approximately
  0.647 mm to the 12 mm sensor limit.
- Real joint-angle/velocity vectors had matching nonzero dimensions.
- Manual and sensory-demo modes completed finite-state runs.
- Habitat throughput was about 0.28x real time, not 1x.

## Separate aerodynamic flight backend

See [FlyBody flight diagnostics](../fly-flight/README.md). This backend has
different units, dependencies, supplied wingbeat data, and explicit
frequency/wing controls. It now supports a published trained controller and
explicit navigation goals, with **7/9** measured-reference benchmark cases
passing. It is not a flight switch for the walking controller, and no
connectome-driven flight policy is implemented.

Flight now accepts this same `habitat.json` through `--scene` in
`straight-goal` mode. Terrain/walls, source markers, lighting, friction,
wind forces, and proxy observations are converted to its centimeter units.
The walking scene is preserved; the flight arena is not silently enlarged.
The flight controller does not yet use habitat sensory proxies or avoid
the obstacles. See the flight guide for boundary reporting and short-run
launch examples.

Both backends use [explicit unit conversion](../../scripts/sim_units.py).
The same microNewton force has different model values in mm/g/s and cm/g/s.
Runs now require exact integer timestep budgets; this fixes a previous
floating-point extra step. Old walking results may contain one extra 100
microsecond step, so endpoint values should be compared at equal step counts,
not assumed identical across this correction.

## Next milestones

1. Profile and accelerate the simulation/controller so measured physical
   throughput reaches at least 1x while preserving numerical settings.
2. Calibrate sensory/environment proxies and make native mouse/physics
   interventions replayable beyond the keyboard schedules.
3. Establish motor-to-body and sensory-to-network interfaces grounded in
   data. The verified sugar-to-MN9 model does not supply a walking controller.
4. Validate those interfaces before claiming closed-loop connectome-driven
   walking or linking anatomical coverage to behavioral fidelity.
5. Benchmark against measured kinematics, contact/slip statistics, perturbation
   recovery, sensory-response latency, and flight stability. Do not claim
   superiority over other demos without common data and matched comparisons.
