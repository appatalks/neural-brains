# Virtual finger and live giant-fiber diagnostic

The standard walking/finger integration below remains a GF readout only.
A separate [experimental physical takeoff demo](hybrid-physical-takeoff.md)
was subsequently approved and tested; its motor assistance is not biological
VNC/muscle decoding and does not change this diagnostic's scope.

Launch the persistent environment-only habitat with:

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --virtual-finger --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/finger-session-001"
```

For plants, fruit, varied surfaces and matched food exposure, use the
[planted habitat launch](planted-habitat.md). Finger/object controls are
unchanged; the existing small-object editor does not edit plants.

**H** or the Finger button enables/disables the physical finger. Move the
pointer over the ground-world image in the single browser app to target a
sphere at **z = 1.5 mm**. The camera projection
intersects that horizontal arena plane, and the target is clamped within
arena XY bounds. The finger moves at at most **20 mm/s of simulated time**,
not an instantaneous pose jump across the arena.

The visible shape now includes a capsule shaft above the rounded tip, rather
than only a ball. The shaft is visual-only; the tip remains the physical
contact shape. This is a stylized single finger, not an articulated hand.

Projection includes camera-frustum center and logical-window/framebuffer
scaling. A cyan target marker follows the requested position immediately;
the physical tip trails that marker according to its speed cap. The overlay
reports the lag in millimeters. Apparent separation during movement is not
removed by teleporting the physical contact object.

## Add scene objects

With the virtual-finger scene enabled, move the pointer over the arena:

- **1:** place a cube at the pointer target.
- **2:** place a sphere at the pointer target.
- **3:** remove the most recently placed object.

There are three slots per type, each with 0.8 mm half-size/radius.
Objects rest at the ground plane and are clamped within arena bounds.
They are static physical obstacles, not dynamic rigid bodies or freehand
meshes. They affect contact/range observations; placement inside the fly
or another object is not yet collision-prevented, so place away from bodies.
Rejected edits (full slots, absent pointer target) produce explicit warnings.

`objects.json` is updated after each edit and saved in the run's external
directory. Reload a saved placement set:

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --virtual-finger --objects /path/to/previous-run/objects.json \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/object-session-001"
```

Slots, sizes, kinds, and positions must match the supported contract; no
unknown object fields or silent substitutes are accepted.

The finger has collision/contact geometry with the fly. It is an external
mocap sphere, **not** a biomechanically modeled human hand. Geometry radius
is 1.5 mm. Camera orbit/pan/zoom remain native; finger targeting follows the
changed camera projection. Disable H before manipulating the camera if you
don't want a simultaneous physical finger movement.

The browser app uses normalized image coordinates and does not need X11
pointer capture. The legacy `--native-window` implementation uses `xdotool`
and X11 coordinates; missing tools/window errors fail explicitly. Neither
interface currently supports finger height adjustment.
Moving the pointer outside the window retains the last target; H removes
the finger below the arena. Native physics editing remains guarded.

## Actual neural computation

The main habitat now applies [spherical optical geometry and eye visibility/
occlusion checks](biological-fidelity-progress.md). Its size feature uses
`2 asin(radius/distance)` and suppresses invisible/occluded approaches.
The rate/threshold encoder remains uncalibrated; this correction is not a
biological response fit.

The worker verifies historical version-630 annotations and selects **314
LC4/LPLC2 neurons plus bilateral GF/DNp01 readouts**. The original recurrent
chemical-connectivity network remains intact.

The finger's angular size and expansion velocity, relative to each eye,
are logged with separate visibility histories. An approximate gate activates
if at least one eye sees an unoccluded approach with:

- angular size >=0.1 rad; and
- positive angular expansion >0.05 rad/s.

This is an **engineering encoder**, not a calibrated biological feature
model, retinal looming projection, LC4/LPLC2 response curve, or a takeoff
trigger. It gates independent 100 Hz Poisson inputs to the verified visual
populations. The shared PoissonGroup input avoids compiling hundreds of
separate PoissonInput objects, but is not bit-identical to the original
diagnostic's generator. Both produce actual network spikes; do not compare
their counts as if they were identical stochastic implementations.

The neural worker returns actual giant-fiber spike counts for every interval
alongside MN9/network counts. It retains neural state after approach stops.
The viewer shows GF activity; `neural-feeding.jsonl` now includes finger
position, angular features, encoder gate and actual GF counts.

**No body lift, flight-policy switch, or motor takeoff is connected.** The
required electrical/VNC/muscle decoding remains missing. GF activity is
evidence of computation under an approximate input, not natural escape flight.

## Validation

- Real MuJoCo contact pairs exist between the finger sphere and fly.
- Compiled model contains the finger shaft and six physical object slots.
- Native pointer interaction created and saved a cube and sphere.
- Saved placement round-trip tests and slot exhaustion checks pass.
- Projection/unit tests check the horizontal-plane target and pointer bounds.
- Static/retreating input does not activate the approximate expansion gate.
- With takeoff inputs enabled, no-input control was silent.
- One-second artificial visual activation produced **172 right GF** and
  **154 left GF** spikes, with actual network counts.
- The original feeding-only worker remains available without
  `--virtual-finger`; additional visual inputs are opt-in.

The first live feature gate did not limit the stimulus to the visual field;
the main habitat now uses eye direction/FOV and center-ray occlusion.
Matching measured response curves remains required before interpreting a
natural looming response. Contact can perturb the body independently of GF, and is not
evidence that GF generated the physical movement.
