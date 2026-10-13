# Experimental physical takeoff and continued flight

The user explicitly approved a hybrid handoff while retaining the missing
biological motor-decoding limitations. This implementation is separate from
the validated brain-only diagnostics and walking habitat.

## What now works

1. A single FlyBody model starts low enough to settle into real floor contact.
2. An approaching virtual finger activates the approximate looming encoder.
3. The actual version-630 FlyWire network produces giant-fiber spikes.
4. A nonzero GF count initiates the **engineered launch controller** at the
   interval boundary after those spikes were observed.
5. External translational and attitude forces act for **0.3 seconds**.
6. Those forces turn off; the published wingbeat/flight policy continues
   operating on the same body's actual state.

Gravity remains enabled. No body pose/velocity assignment occurs at the
neural transition. Desired reference positions change, not the physical
position. The virtual finger is an external physical object, not a neural
motor force or measured predator.

**This is not physiological electrical/VNC/muscle decoding.** The temporary
force/torque controller is an explicit stand-in for that missing motor model.
The learned flight policy uses synthetic future-reference goals; it is not
the connectome. The body has retracted legs, not the existing walking-gait
controller. Landing and complete walking-to-flight transitions remain missing.

## Start the visible demonstration

```bash
.venv-flight-py311/bin/python scripts/fly_takeoff.py \
  --test-approach --seconds 1.5 --arena-half-size-mm 300 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/hybrid-takeoff/interactive-001"
```

`--test-approach` is an explicitly scheduled environmental approach, not an
automatic timer that launches the fly. Without GF spikes the body stays
grounded and no launch assistance is applied.
The simulation runs slower than real time. The viewer retains the final
state after its interval; Q/window close saves and exits.
`--exit-on-complete` is available for deliberate auto-closing tests.

For pointer-controlled interaction instead of the test stimulus:

```bash
.venv-flight-py311/bin/python scripts/fly_takeoff.py \
  --seconds 3 --arena-half-size-mm 600 \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/hybrid-takeoff/pointer-001"
```

H enables the finger; P/Space pauses; Q closes. The finger target is on a
5 mm-high plane and has a bounded physical speed. The observer camera follows
the body for flight inspection. This prototype does not yet expose the full
walking habitat object editor or retina panel.
Only the fixed 1.5-second test was validated, not every pointer trajectory,
seed, duration, or goal.

The copied habitat's terrain and lights are included. The arena half-size
override is explicit: 300 mm is needed for the measured test's roughly
274 mm flight path. The original 30 mm half-size is preserved as the default;
running long fast flight inside it does not satisfy the bounded-arena check.

## Verified result

Fixed environmental approach, 1.5 simulated seconds, seed-420 neural worker:

| Measure | Result |
| --- | --- |
| Initial physical ground contact | Observed |
| Actual GF-triggered initiation | 0.14 s |
| Launch assistance | 0.3 s, then off |
| Continued flight after assistance | 5,300 control steps / 1.06 s |
| Final thorax height | Approximately 0.985 cm |
| Post-assistance floor contact | None |
| Explicit arena boundary exit | None |
| Runtime body pose reset | None |

The engineering acceptance criterion requires initial floor contact and
at least 0.5 seconds after assistance with thorax height above 0.5 cm,
no floor contacts, and no arena exits. It is **not** a biological fidelity
criterion or universal flight-stability claim.

A no-approach control remained grounded with zero GF spikes, no launch
forces, and no flight. Earlier failed prototypes were retained: the upstream
airborne task disables ground collisions, so grounded launch must enable
contacts **before compilation**, not merely edit masks afterward.

The native viewer also passed the same fixed 1.5-second physical test and
exited cleanly. The older flight viewer has a different pointer API from
the walking viewer; its explicit X11 window rectangle is used for pointer
projection. High-DPI behavior in that older backend is not generally verified.

## Logs and reproducibility

Each external run saves:

- `environment.json`: explicit habitat/arena dimensions.
- `brain-metadata.json`: real input/readout IDs and source revision.
- `takeoff.jsonl`: actual GF responses, looming features, physical position/
  velocity, phase, assistance force/torque and contact count.
- `summary.json`, `status.json`, and a rendered `preview.png`.
- Worker diagnostics remain in `brain-worker.log`.

Neural and physics intervals are 10 ms, with a 0.2 ms motor-control timestep.
The neural response is obtained first; launch is deferred until that physical
interval completes, avoiding motor action based on future interval spikes.
The next interval executes the motor assistance.
Initial low-body pose assignment is a disclosed initial condition only,
not a runtime takeoff teleport.

The force controller's gains and body mass/inertia hash are recorded. It
uses the model's actual mass, caps translational forces, and applies an
orientation-stabilizing torque. That torque is not a measured muscle effort.
The original gravity and electrical/muscle evidence gaps remain explicit.

## Next steps

Replace the assistance with grounded jump/wing-deployment muscle actuation,
calibrate looming feature encoding, validate electrical/VNC transmission,
and integrate a compatible walking/landing model.
Keep this functional hybrid benchmark as a comparison; do not relabel it
biologically complete when those steps are still missing.
