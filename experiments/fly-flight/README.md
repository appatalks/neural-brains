# Aerodynamic flight: diagnostic and published-policy modes

This integrates [FlyBody](https://github.com/TuragaLab/flybody/tree/d015e9bfe441bd90ae431bac24c55cb74bdbce26)
and its MuJoCo wing-fluid model. It now supports the published trained
reference-tracking policy as well as the original diagnostic mode.
It is **not universally robust or connectome-controlled flight**.

Measured-reference benchmarking passes **7/9** configured cases, retaining
two explicit failures. A separate one-second synthetic-goal test passes
local tracking criteria. Flight uses real wing-fluid interaction, not
gravity toggles or animated walking-model wings.

## Scientific inputs and license

Provider: [FlyBody supplementary datasets](https://doi.org/10.25378/janelia.25309105).
The [catalog](../../research/sources.json) records Figshare file ID
51196859, size **12,880,076 bytes**, MD5, and license:

- `datasets_flight-imitation.zip` includes
  `flight-dataset_saccade-evasion_augmented.hdf5` and `wing_pattern_fmech.npy`.
- `trained-fly-policies.zip` is **6,537,720 bytes**, with provider-supplied
  MD5 `12934d5a1c60631a710bc2b6d297d3ce`. Only the inspected flight SavedModel
  and two variable files are extracted; unrelated policies are not extracted.
- Provider metadata reports **GPL-3.0+ for the data**, distinct from
  Apache-2.0 for upstream software. Preserve the separate terms/attribution.

```bash
python3 scripts/datasets.py fetch flybody-flight-imitation \
  --asset datasets_flight-imitation.zip --data-dir "$FLY_DATA_DIR"
python3 scripts/datasets.py fetch flybody-flight-imitation \
  --asset trained-fly-policies.zip --data-dir "$FLY_DATA_DIR"
```

The runner verifies archive size, upstream MD5, and receipt. It extracts only
the two inspected filenames after checking exact uncompressed sizes.
Existing files/manifests must match and are never silently overwritten.
The supplied wing pattern is used explicitly; no generated fallback is used.
Its filename does not establish direct empirical measurement; further
methods review is needed for that claim.

## Separate environment and diagnostic

```bash
uv venv --python python3.11 .venv-flight-py311
uv pip install --python .venv-flight-py311/bin/python \
  -r experiments/fly-flight/requirements.lock.txt

MUJOCO_GL=egl .venv-flight-py311/bin/python scripts/fly_flight.py \
  --headless --seconds 0.05 --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/aerodynamics-001"
```

Use a new output directory. The flight environment uses Python 3.11 and pins FlyBody revision
`d015e9bfe441bd90ae431bac24c55cb74bdbce26`, dm-control 1.0.27,
MuJoCo 3.2.7, and NumPy 1.26.4. It is separate from both neural and
walking environments.

Measured-reference mode is limited to **0.6 simulated seconds** and to the
selected recording's usable duration. Trajectory 0 supports only about
0.1892 seconds after accounting for the policy's future-reference window.
Requests beyond the recording fail explicitly; data are never repeated or
extended silently. Trajectory 48 supports about 0.575 seconds.
Durations must be exact multiples of the 200 microsecond control timestep.

This model uses **centimeters, grams, seconds**, unlike walking's
millimeters/grams/seconds. Gravity is 981 cm/s2 and fluid density is
0.00128 g/cm3. Convert units explicitly before sharing scene/control data.

Two wing geometries have ellipsoid-fluid interaction enabled. In diagnostic
mode, zero residual actions plus the wingbeat generator are not a trained
policy. In trained mode, the published policy consumes both proprioceptive/
kinematic observations and **privileged future-reference signals**. Those
references are not visual perception or a reconstructed biological brain.

## Run the published controller

```bash
MUJOCO_GL=egl .venv-flight-py311/bin/python scripts/fly_flight.py \
  --headless --controller trained --trajectory 48 --seconds 0.5 --seed 0 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/trained-001"
```

The secured flight environment pins **TensorFlow CPU 2.18.1**, Keras 3.15.0
and protobuf 5.29.6. It does not load the source SavedModel directly: its
historical `Independent_ACTTypeSpec` is not registered by current TensorFlow
Probability. Instead, create a checksum-bound, float32 TFLite export of each
policy's mean-action function once, using the previously verified legacy
environment only for this offline conversion:

```bash
.venv-flight/bin/python scripts/convert_fly_policy_tflite.py \
  --data-dir "$FLY_DATA_DIR"
.venv-flight-py311/bin/python scripts/test_fly_policy_tflite.py \
  --data-dir "$FLY_DATA_DIR"
```

The converter validates the original provider archive and refuses to
overwrite an existing export. The TFLite files, synthetic parity inputs and
receipts are stored under `$FLY_DATA_DIR/derived`, outside Git. The old
`.venv-flight` contains vulnerable legacy dependencies; use it only for this
trusted, local conversion and never as the normal runtime. The application and
simulation scripts use `.venv-flight-py311`. They have no fallback if the
verified converted artifacts are missing or invalid.

The secure runtime was parity-checked against the source-version mean actions
for 32 deterministic synthetic observations per policy. Maximum clipped
canonical-action differences were **7.64e-7 flight** and **8.71e-5 walking**,
within the declared 1e-4 threshold. A bounded one-second straight-goal flight
then completed 5,000 steps with 0.02716 cm RMS position error, 8.89 degree
maximum orientation error and no floor contacts; a separate one-second
walking check remained upright (0.9956) with unchanged mass/inertia. These
are controller-parity and bounded engineering checks, not broad robustness or
biological validation. The full conversion report and trial outputs remain in
the external data directory.
Synchronize an existing environment rather than retaining incompatible
extra packages:

```bash
uv pip sync --python .venv-flight-py311/bin/python experiments/fly-flight/requirements.lock.txt
```

Inference follows the published test wrapper: float32 batched observations,
the distribution **mean** rather than sampling, canonical clipping, and
affine conversion to physical action bounds. The TFLite runtime uses one CPU
thread; the exact source SavedModel remains preserved in the verified archive.

Raw wing/frequency inputs are disabled by default in trained mode.
W/S/A/D are not game-style navigation keys; pressing them produces an explicit
warning and logged ignored event. Use `--allow-wing-overrides` only for
deliberate experiments. Then they become additive residuals that can impair
tracking. Bounds are enforced and failed tracking returns a nonzero exit code.

### Longer explicit navigation goals

The source provides a public inference trajectory generator. We use it to
construct an **explicit synthetic goal**, rather than pretending short
scientific recordings cover a longer flight:

```bash
.venv-flight-py311/bin/python scripts/fly_flight.py \
  --controller trained --reference straight-goal \
  --seconds 1 --speed-cm-s 20 --height-cm 1 --yaw-rate-rad-s 0 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/goal-interactive-001"
```

This example starts automatically. Add `--start-paused` only when you want to
inspect the model first; focus the flight window and press **P or Space** to
begin. The visible label displays paused/running state and simulation time.
The one-second physical interval ends after 5,000 control steps. The viewer
now stays open for inspection instead of disappearing. **Q** or window close
ends the session and writes final results. `--exit-on-complete` restores
automatic closure for deliberate bounded viewer tests.

At the end, `DONE` means the requested interval stopped, not that all
scientific checks passed. `STOPPED` indicates early termination or observed
boundary exit. No more physical time advances in the held result; another
trial requires a new launch/output directory. Headless behavior is unchanged.
This is distinct from the walking habitat's `--until-closed` mode, which
continues active simulation until closed.

The held-viewer test completed 250 flight control steps, remained open with
`awaiting_viewer_close` status, and saved its final successful interval on Q.
Holding the scene does not extend the validated flight or fabricate more
physical steps.

`speed-cm-s`, `height-cm`, and `yaw-rate-rad-s` are startup goal parameters.
Nonzero heading rate creates a turning goal. Numeric bounds are not a
validated operating envelope. The CLI permits up to 60 simulated seconds
in goal mode, but current verification covers **one second**, not every
longer duration, heading, height, speed, or initial phase.

One-second goal test, seed 0, 20 cm/s, 1 cm target height:

- Completed exactly **5,000 control steps**.
- Position tracking RMS **0.02716 cm (0.2716 mm)**.
- Maximum reference-relative orientation error **8.89 degrees**.
- Zero floor-contact steps.
- The native viewer also completed this goal after exercising frequency,
  wing-roll, neutralization, and resume controls while initially paused.
  Its scientific outputs matched the headless test.

This enables a high-level goal interface, not biological decision-making.
The generated goals remain privileged inputs to the learned controller.
They can now run in the shared walking habitat, but the habitat's sensory
observations do not drive this policy. They are not connected to FlyWire.

## Shared walking and flight habitat

Both backends now accept the same
[habitat.json](../fly-walking/habitat.json) configuration. For a short flight
within the unchanged arena:

```bash
.venv-flight-py311/bin/python scripts/fly_flight.py \
  --controller trained --reference straight-goal \
  --scene experiments/fly-walking/habitat.json \
  --seconds 0.1 --speed-cm-s 20 --height-cm 1 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/shared-habitat-001"
```

The shared configuration supplies the physical bar/ramp/rock, walls,
surface friction, lights and source markers. Flight converts lengths from
millimeters to centimeters. Its camera starts wider to show the environment;
mouse zoom/orbit remains available. The walking configuration is unchanged.

Flight also records the same uncalibrated Gaussian odor/light proxies and
environment-range rays, and applies the configured capped thorax wind drag
using unit-correct forces. These proxies retain all the limitations described
in the walking guide: they are not physiological receptors, compound-eye
vision, CFD, or a connectomic sensory encoder. Their observations are logged,
not passed to the reference-tracking neural network.

Each scene run saves `environment.json`, the source scene hash, and arena
adapter hash. Observations include a `habitat` record with millimeter position,
odor/light channels, proximity and XY-boundary state. Control-step records
include terrain/wall/floor contact counts, wind force and boundary status.
The summary reports first boundary exit and contact-step counts.

**The existing arena is 60 x 60 mm, with 3 mm walls.** A 20 cm/s flight goal
traverses 200 mm in one second, at a default height of 10 mm above those walls.
The run does not silently enlarge the arena or change the target.
At 0.2 seconds, the test explicitly reported a boundary exit at approximately
0.1512 seconds and returned exit code 4. A short 50 ms run remained inside,
rendered the shared environment, and passed finite-state/geometry checks.

For longer flight, explicitly edit a copied scene's dimensions/goal.
Different speed/height/heading goals are not all validated, and this policy
does not automatically avoid terrain. A boundary exit is reported, not
interpreted as successful habitat navigation. Scene mode is currently
supported only with `--reference straight-goal`; measured-reference benchmarks
continue using their original arena.

This shares the environmental description, not the body model: walking and
flight still use separate physics/controller backends. Walking-to-flight
transitions, landing, and simultaneous use of walking-controller keyboard
terrain schedules in flight remain unimplemented.

## Robustness benchmark and known failures

Run the fixed [benchmark](benchmark.json):

```bash
.venv-flight-py311/bin/python scripts/benchmark_fly_flight.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/benchmark-001"
```

Local engineering thresholds were selected before evaluating the cases:
complete the requested duration, RMS position error <= **0.1 cm**, maximum
reference-relative orientation error <= **45 degrees**, and no floor contacts.
These are not paper-derived biological fidelity criteria.

Final result: **7/9 passed**, with consistent runner/policy/unit-module
hashes and matching requested parameters:

- Trajectory 48, seeds 0-3: passed 500 ms tracking.
- Trajectory 48, seed 4: lost control and terminated at about **80.6 ms**;
  initial discrete wing-phase index **22**.
- Trajectory 0, seed 0: passed its 180 ms test.
- Trajectory 57, seed 0: completed 500 ms but reached approximately
  **56.0 degrees** orientation error; failed the threshold.
- Trajectory 140, seed 0: passed 500 ms tracking.
- Trajectory 48 with a **2 microNewton** lateral force for **50 ms**:
  passed, with position RMS about **0.3643 mm**.

Seeds 0/3 selected phase index 13 and seeds 1/2 selected index 10: five seeds
are not five distinct wing phases. We preserve the failing phase, reference,
and original thresholds; they are not filtered out to inflate the score.
The benchmark intentionally returns a failure code while cases remain failed.

Use `--gust-uN 2 --gust-at-s 0.2 --gust-duration-s 0.05` for the force test.
This is an explicitly applied force, **not calibrated airflow/CFD**.
The shared [unit module](../../scripts/sim_units.py) converts 2 microNewtons
to 0.2 g*cm/s2 in flight; the same force is 2 g*mm/s2 in walking.
Both backends now use exact integer step budgets, fixing occasional
floating-point extra steps.

## Native viewer and control ports

```bash
.venv-flight-py311/bin/python scripts/fly_flight.py \
  --start-paused --seconds 0.05 --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-flight/interactive-001"
```

Start paused to inspect the short diagnostic.
Focus the **flight** MuJoCo window:

| Key | Meaning |
| --- | --- |
| W / S | Raw frequency modulation; diagnostic mode or explicit override opt-in only |
| A / D | Raw opposite wing-roll residuals; diagnostic mode or explicit override opt-in only |
| X | Neutralize both commands |
| P / Space | Application pause/resume during the active interval |
| Q | Close and save; also available after the interval ends |
| Mouse | Native camera/body inspection |

Commands map by upstream action **names**, not guessed indices, and are
checked against the action specification. They are actuator/generator
commands, not mapped neural firing rates.
The older flight viewer lacks a 2D application-overlay API. A centered 3D
status label now shows paused/running state and simulation time; events and
warnings also print to the terminal.

The native simulation/control panels are hidden. Native reset/play controls
can otherwise mutate raw MuJoCo data without resetting Composer's task,
wingbeat generator, and policy inputs. The application now guards its
integration state and rejects/logs those physics edits, keeping pose, velocity,
and clock synchronized. Relaunch with a new output directory to reset.
Camera controls remain available; native physics edits are not supported.

On 2026-10-10, a user's run reproduced this failure: it remained paused,
then terminated after one control step from a default near-ground pose.
Validation of the fix attempted a native Backspace reset while paused, then
resumed with Space. The reset was rejected, and the full 5,000-step goal
completed with the same final state as the headless baseline.

## Outputs and measured checks

External outputs include `observations.jsonl`, `summary.json`, `preview.png`,
`control_steps.jsonl`, and explicit `status.json`. They retain motor commands, kinematic/
proprioceptive signals, task references, source revision, checksum,
physics units, fluid state, action names, and termination status.
Control records distinguish the issued policy action from the task's
wingbeat-adjusted action, which the upstream task modifies in place.
Tracking metrics, clipping counts, phase index, physical force, module
hashes, and inference/physics timings are also saved.

On 2026-10-10:

- A 50 ms diagnostic completed with finite state and two aerodynamic wing
  geometries.
- Thorax height changed from approximately **0.537 cm to 0.428 cm** with
  neutral residuals. This does **not** establish stable hover or controlled
  flight.
- The final body-z/world-z dot product was **-0.413**, showing substantial
  attitude loss. The renderer confirms tumbling rather than stable flight.
  Stability is explicitly marked unvalidated in the result.
- Physics timestep was **50 microseconds**, control timestep **200
  microseconds**, and the supplied baseline wingbeat frequency **218 Hz**.
- Native viewer opened paused; frequency, differential-roll, neutralization,
  and resume keys were exercised and recorded. It exited with code 0.
- Its final body position matched the neutral headless diagnostic.

## Remaining limitations

| Limitation | Current status |
| --- | --- |
| Uncontrolled wingbeat-only flight | Published controller now available; diagnostic mode retained explicitly |
| Robustness across phases/references | **Not solved:** two measured benchmark failures retained |
| Short measured recordings | Longer explicit synthetic goals supported; not equivalent to measured behavior |
| Real-time throughput | **Not solved:** one-second goal took about 11.8 wall seconds in the test; timings include setup |
| Neural/body coupling | **Not implemented:** controller is learned, not connectomic |
| Shared walking/flight environment | Same scene configuration now supplies converted physical geometry, fields and wind; controller/body transitions remain |
| Biological vision/olfaction and calibrated sensory encoders | Remain unvalidated or unimplemented |
| Takeoff/landing and walking-to-flight transitions | Not implemented |
| Physiological muscles and neuromodulatory state | Not established by these body/controller models |
| "Most realistic" comparison | Requires matched empirical data and metrics, not appearance |

In the one-second test, policy inference took about **1.57 s** and environment/
physics stepping about **8.42 s**. Body/environment execution dominates;
accelerating only the neural network will not achieve real time.
Newer controller-reuse checkpoints exist upstream but have not been executed.

Do not substitute a hand-designed stabilizer and describe it as a reproduced
neural controller.
