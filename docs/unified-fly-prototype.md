# Single-body walking and flight prototype

The user selected a single FlyBody model with legs and wings, rather than
transferring state between incompatible FlyGym and FlyBody bodies.
[fly_unified.py](../scripts/fly_unified.py) is a separate experimental
integration. The existing autonomous habitat is unchanged.

## Implemented

- One compiled physical body retains legs, wing joints, ground contacts,
  mass and inertia throughout the experiment.
- The checksum-verified published walking and flight policies are extracted
  separately, preserving the existing flight extraction receipt.
- Motor channels and observed joints are matched by exact names, not assumed
  array offsets. The walking policy observes 85 joints and 59 filtered
  activation channels; the flight policy observes its 25 trained joints and
  no activation channels. Other body channels remain physically present.
- Walking actions update every 2 ms; flight actions every 0.2 ms. Physics
  uses the existing flight timestep of 0.05 ms. Walking sensors therefore
  differ in averaging cadence from the original walking training setup.
- Grounded walking precedes actual GF-triggered assisted takeoff. The test
  explicitly gates visual-population Poisson inputs between 0.3 and 0.4 s:
  this is a diagnostic neural stimulus, not a retinally calibrated approach.
- The handoff changes controller references/phase only. Position and velocity
  are checked for exact preservation. External assistance lasts 0.3 s,
  then switches off and the learned flight controller continues.
- Native observer graphics and free camera are available with `--view`.
  P/Space pauses, C toggles tracking, Q saves/closes. A bounded viewer retains
  the result for inspection. Native physics edits remain guarded.

There is no claim of biological motor decoding. Future-reference signals,
actuator position control, wing pattern generation and launch assistance
remain explicit engineered/learned components.

## Reproduce

Use a new external output directory for each test.

```bash
# Grounded walking on the legs-and-wings body.
MUJOCO_GL=egl .venv-flight/bin/python scripts/fly_unified.py \
  --seconds 1 --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/walking-check-001"

# Same-body walking, real GF initiation, assisted takeoff, continued flight.
# Arena enlargement is explicit, not a silent fix for fast flight.
.venv-flight/bin/python scripts/fly_unified.py \
  --view --takeoff-test --seconds 1.5 --arena-half-size-mm 300 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/takeoff-check-001"
```

`--airborne-diagnostic` initializes an airborne body explicitly; it is not
evidence of takeoff. `--landing-test` requires `--takeoff-test` and at least
2.5 seconds; it is an experimental synthetic descent and currently fails.
Do not use it as the normal polished habitat.

## Verified real-physics results

Results are retained under the selected external data root:

| Test | Result |
| --- | --- |
| `walking-002`, 1 s | 2.025 cm forward; upright cosine 0.9968; maximum reference error 0.0429 cm |
| `flight-001`, initialized airborne, 0.5 s | Flight tracking worked with legs physically retained; original small arena was exited, so this is not a bounded-habitat pass |
| `flight-002`, initialized airborne, 0.5 s, 150 mm half-size | Passed corrected bounded-arena check: maximum error 0.0408 cm, zero floor contacts/exits |
| `walk-takeoff-002`, 1.5 s, 300 mm half-size | GF initiation 0.32 s; exact qpos/qvel preservation; 4,399 post-assistance flight steps (0.8798 s); zero flight floor-contact steps and arena exits |
| `landing-001` / `landing-002` | Failed to regain sustained upright ground contact; no hidden reset |
| `landing-003`, actuator-only leg deployment | Still failed and worsened attitude; failed trial retained, deployment variant not adopted |
| `native-takeoff-001` | Native single-body walking-to-flight check passed; real window responsiveness verified; result retained for inspection |

The first walking trial exposed an initial-position live-array alias in
measurement; that measurement bug was fixed and a fresh trial rerun.
The original small-arena takeoff trial exited the arena; acceptance now
requires zero exits, rather than treating uninterrupted flight as sufficient.

## Still missing before replacing the main habitat

- Successful sustained landing and walking re-entry, without pose/velocity
  assignment or hidden forces.
- Robust recovery on this body and multiple-condition transition benchmarks.
- The environment-driven finger/eye encoder, feeding, objects and stable
  companion dashboard on this backend. They remain available in the existing
  FlyGym habitat, not yet in this diagnostic.
- Broader native interaction/shutdown testing and measured long-session performance.
- Neural/VNC/muscle decoding and empirical validation.

No failing landing trial is counted as a completed walking-flight cycle.
