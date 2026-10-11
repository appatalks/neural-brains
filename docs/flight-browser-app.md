# Experimental flight-capable browser app

## Newly approved functional controls

The user next requested the most natural brain-linked landing response.
The opt-in [brain-linked reduced landing cycle](brain-linked-landing.md)
uses actual DNp10 spikes during flight for initiation, approximate physical
surface input, disclosed descent assistance and physical contact/release
gates. It now reaches stable contact and unassisted learned walking in bounded
tests; DN silencing prevents the cycle. It is **not calibrated biological
landing**. Its walking-boundary reference is engineered.
The new options are `--brain-linked-landing --landing-surface-vision`; earlier
failed timer-based engineered landing remains separate and disabled.

An off-center takeoff fix now preserves measured body heading in the launch
reference and uses that reference's world velocity in assistance. Near arena
edges, explicit engineered clearance feedback limits forward travel until
there is room to turn. This corrects a live corner-launch failure; it does
not replace GF neural initiation or remove the emergency safety stop. See
[launch-clearance measurements](flight-avoidance.md).

The next user-selected environment is the
[225 mm compact grassland](grassland-habitat.md), 25% smaller in each horizontal
dimension than the previous 300 mm arena. Unified defaults now select the
version-3 scene, matched fruit exposure and 112.5 mm half-size. Grass, leaves,
soil/fruit/stone surfaces have actual contact geometry, and free-body seeds
can be physically displaced. Contact telemetry is separate from neural counts.
The smaller arena uses a 15 cm/s engineering reference to retain stable
turns/launch; the 150 mm-half-size comparison retains 20 cm/s.
Original planted scenes and failed experiments remain available.

The user then reported persistent boundary freezes and selected an explicit
[predictive flight-avoidance comparison](flight-avoidance.md).
`--flight-avoidance` now provides measured-state-dependent turning references
through the existing wing policy. It uses privileged arena bounds and
ray-detected geometry memory, not neural or calibrated retinal steering.
Final physical tests include 20 s of flight, distinct physical wing phases,
repeated obstacle avoidance and exact replay. This is not organic flight.
The same ongoing app uses this option, while the emergency boundary stop
remains for failures. Failed engineered landing experiments remain separate.

The later [reduced DNp10 leg-extension increment](neural-leg-extension.md) is
available as opt-in `--neural-leg-extension` on this app and the unified main
launcher. Actual verified DN spikes drive an assumed bilateral activation
surrogate into existing leg position actuators **during flight only**. It adds
no external extension force, pose reset, wing controller or touchdown claim.
The baseline stays off, and it cannot be combined with experimental engineered
landing. DNp07 and the ambiguous steering pairs remain readouts.

The next approved [continuous spherical-vision option](graded-visual-feedback.md)
adds `--graded-vision` to the same unified app. Actual physical spheres, eye
poses and occlusion produce continuously varying LC4/LPLC2 input rates using
explicitly assumed curves. Saved spheres are sensory sources; non-spherical
geometry currently only occludes them. The binary encoder remains the default.
This is not calibrated retina, full optic flow or natural landing vision.

The user subsequently approved **explicitly engineered steering and landing**
to complete a usable experience while biological decoding remains unfinished.
The opt-in `--engineered-navigation` flight-app experiment uses a smooth curved
flight reference and external force/torque-assisted descent. It has not yet
replaced the live comparison app.

The first landing trials produced physical contact but unstable body attitude;
one later trial achieved upright contact but tumbled after abrupt assistance
removal. These failed bundles remain under `engineered-cycle-001` through
`engineered-cycle-007`. They are not successful landing-cycle evidence.
Later trials also failed sustained unassisted walking, and one aggressive
attitude-gain trial failed with invalid physics acceleration. That variant was
not retained. The validated interactive app does not enable these experiments.
Summary fields distinguish an enabled experimental landing controller from
validated landing; controller presence is not evidence of completion.

The cycle acceptance gate requires actual initial ground contact, preserved
qpos/qvel at takeoff, at least 0.5 s of airborne flight without floor contacts,
no boundary safety stop, sustained stable touchdown, and at least 0.3 s of
upright post-landing walking **after landing assistance has been removed**.
Touchdown height alone cannot pass. Source navigation/controller hashes and
applied force/torque are retained in experiment outputs.

These controls are not neural navigation or muscle physiology. The neural-only
research track and prior failure evidence remain available.

The user explicitly approved switching the browser experience to the
single-body FlyBody prototype. The original walking habitat remains available
as a comparison; the new backend is not a completed biological animal.

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified \
  --scene experiments/fly-walking/planted-habitat.json \
  --feeding-config experiments/flywire-sugar/planted-feeding.json \
  --objects /path/to/previous/objects.json \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/interactive-session-001"
```

The launcher invokes the existing isolated flight Python environment, not a
mixed FlyGym/TensorFlow installation. The single app remains at
**http://127.0.0.1:8840/**. No native viewer opens.

The app/main launcher now **reject alternate ports and port 0**. Interactive
dashboard instances use the same central `DEFAULT_PORT=8840`. An occupied port
fails explicitly; there is no alternate-version fallback. Bounded physical
browser tests must use that port sequentially, not run alongside a live app.
Read-only HTTP unit-test fixtures do not run a fly or neural worker.

## Connected in this backend

- One physical body has active legs and wings throughout walking and flight.
- Independent observer camera rendering, eye views, real full-brain interval
  counts, neuron selection and verified chemical connections.
- Shared plants/materials, preserved edited cubes/spheres, source food
  exposure and existing light/odor scene markers.
- Camera orbit/pan/zoom, pause, explicit reset, sugar/friction toggles,
  external push, physical pointer finger and saved object edits.
- H/Finger enables the finger. Its target plane is 1.5 mm above the floor;
  speed remains capped at 20 mm/s simulated time.
- Visible, unoccluded spherical expansion gates the identified visual inputs.
  Actual GF spikes initiate the motor handoff at the interval boundary.
- External launch assistance lasts 0.3 s; the published flight policy then
  continues on the same physical body's state.

The initial camera tracks the fly closely. The earlier Overview showed a
**150 mm-half-size arena**, reduced from 300 mm at the user's request.
That halved each horizontal dimension (600 mm wide to 300 mm wide), not
just the area. Existing plants and in-bounds edited objects keep their scale
and positions. The current compact grassland further reduces that width to
225 mm; original geometry retains its dimensions. Out-of-bounds saved placements fail validation rather than
being silently moved. `--flight-arena-half-size-mm` remains an explicit override.

The physical finger in normal interactive runs now follows **wall-clock time**
at a capped 20 mm/s, with at most 100 ms of motion credited per update.
This is an external observer intervention, not biological motion; its apparent
speed in simulated time can be higher when physics is slower than real time.
Positions, target, lag, clock choice and credited wall duration are logged.
Pause/safety-stop does not move the physical finger or accumulate a long
catch-up jump. Prescribed approach tests retain the original simulated-time
motion, preserving their stimulus protocol.

Mouse updates are throttled rather than debounced: continuous movement sends
the latest target about every 33 ms instead of waiting for movement to stop.
The body still processes targets at its interval boundaries, so this is not
zero-latency interaction.

## Important limits

Walking/flight are learned motor policies with privileged synthetic references.
GF controls **initiation**, not flight direction or obstacle avoidance.
The visual rate gate is uncalibrated. The preserved default is straight-reference
tracking; the explicit flight-avoidance option supplies engineered turns.
Neither is organic brain-directed navigation.

The eye panels now show FlyBody's 256-by-256 rectilinear eye cameras, not the
FlyGym fisheye/721-ommatidia channels. Their interpretation is labeled.
Food exposure remains a geometric proxy; odor/light are not new calibrated
neural encoders.

Biologically calibrated landing and self-righting are **not implemented**.
The opt-in actual-DNp10 assisted landing model has bounded contact/released-gait
validation, separately labeled from biology. When the
body reaches within 5 mm of the configured XY boundary, the app explicitly
pauses body and brain and reports a safety stop. This is an engineering
freeze, not braking, collision avoidance or landing. Camera inspection
continues; Reset is required to resume a new experiment.
The app labels this **Simulation safety stop**, not an object-edit rejection.
Reducing the arena means the unchanged straight-flight reference reaches
this margin sooner. The new flight-avoidance comparison turns before this
margin in the tested runs; it retains the stop if avoidance fails.
Walking-boundary behavior is not solved by the flight controller.

At a boundary pause the world has a persistent banner explaining that the
app remains open. Resume is disabled because there is no safe navigation
controller; Reset starts an explicitly new experiment. Camera and neural
inspection remain available. Save and stop is a separate action.

## Why the firing map can be silent

The pinned model's no-input baseline is silent; calibrated spontaneous firing
and continuous flight optic-flow encoding are not implemented. Sugar contact
and looming are the currently connected stimuli. The learned motor policy can
continue flying after genuine GF/network activity subsides.

The app now shows total recorded network spikes and firing-interval counts
for the current episode, including intervals missed by display polling.
**Inspect last firing interval** displays the last nonzero packet with an
explicit HISTORICAL label and its simulated time range. **Live interval**
returns to current counts. Reset clears these summaries; repeated pause
heartbeats do not double-count spikes. Only one last-firing packet is retained,
not an unbounded event history, and no artificial firing is introduced.

The **Steering and landing circuit readouts** section adds live counts for
39 version-matched candidates, with explicit ambiguous-identity labels and
click-through connection inspection. It follows the live versus historical
activity selection. These neurons are not silently mapped to wing/leg actions.
Only the explicitly enabled reduced DNp10 option uses its verified pair to
drive physical leg actuators; the motor status labels that assumed boundary.
Physiological decoding remains unfinished.

The previous `interactive-app-002` logs recorded **2,444 network spikes and
22 GF spikes**, with MN9 silent. Its final boundary interval was silent. It
safety-paused first and later received the app's Q/Save-stop input; no runtime
error was recorded. These are measured outputs, not evidence of neural flight
navigation.

The Terrain-bars and playback keys are not supported here and report that
limitation. Plants are static scene objects, not toggled by the terrain key.
There is no direct manual fly steering or flight-mode button.

## Evidence

External runs under `results/fly-unified`:

| Run | Evidence |
| --- | --- |
| `browser-flight-001` | Explicit upstream neural input test: GF handoff, exact qpos/qvel preservation, 4,450 post-assistance flight steps, zero flight floor contacts |
| `browser-approach-001` | Physical finger approach through eye visibility: 7 GF spikes, handoff at 0.14 s, 5,300 post-assistance flight steps (1.06 s), zero flight floor contacts, no boundary stop |
| `browser-no-approach-001` | Ground contact/walking, zero GF spikes, no launch or flight |

All bounded cases retained the physical body's mass/inertia and closed the
renderer/dashboard cleanly. The direct input test is not interchangeable
with the physical approach test. No arbitrary launch timer is used in the
normal interactive app.

The physical approach test is reproducible with
`scripts/fly_flight_app.py --seconds 1.5 --test-approach --dashboard-port 8840`
and explicit external data/output directories. The test uses a prescribed
physical trajectory; it does not prove every user pointer movement triggers
escape or that response timing matches animal measurements.
The existing live app must first be saved/stopped with user approval; tests
must not start a second app on an alternative port.

Still required: held-out perception/behavior validation, flight steering and
navigation circuitry, reliable landing and recovery, broader interactive
reset/perturbation testing and coupled performance improvements.

The user chose to prioritize supported neural steering rather than add another
rule-based navigation controller. See [flight steering evidence](flight-steering-evidence.md).

### Arena and pointer regression checks

- Default launch forwards 150 mm half-size; the live saved scene confirms it.
- Six existing object placements were preserved without repositioning.
- Browser logic tests send 100 continuous pointer events and verify that the
  first scheduled update is not postponed by later motion.
- Motion tests check zero duration/distance, nonfinite inputs, target clamping
  by distance, 20 mm/s wall-time speed and the 100 ms catch-up limit.
- Live consecutive finger-active intervals obeyed the logged wall-time cap.
- The prescribed simulated-time approach benchmark remains unchanged in its
  explicitly 300 mm test arena: handoff 0.14 s, 5,300 post-assistance flight
  steps. Evidence: `results/fly-unified/pointer-protocol-parity-001`.
