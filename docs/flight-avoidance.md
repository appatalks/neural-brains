# Predictive flight avoidance: functional engineered comparison

The user reported that straight-reference flight still reached a boundary and
froze, and explicitly selected an **engineered avoidance comparison** to fix
that usability problem. This increment changes directional flight references
and verifies the resulting physical motion. It does not call the result
organic, connectome-controlled flight or biological navigation.

## Root cause and scope

The existing GF circuit initiates assisted takeoff. Afterwards the learned
wing policy followed a straight reference that continued through the arena.
The 5 mm boundary margin correctly exposed the missing navigation controller:
it froze physics and brain rather than pretending to brake or land.

### Off-center takeoff regression and correction

The later live `interactive-app-011` failed at 45.13 s **during assisted
launch**, not normal flight. Walking had reached about [67.5, 96.5] mm before
finger-driven GF takeoff. The handoff reset the synthetic heading to world
+X regardless of the measured body heading; launch assistance also used a
fixed [20, 0, 0] cm/s velocity term. That drove the body toward the corner
before ordinary flight avoidance had enough room to turn.

The corrected app initializes only the **controller reference** from measured
body yaw. Its launch assistance follows that reference's world velocity rather
than an unconditional +X term. A declared engineered launch-clearance guard
starts forward reference speed at zero, allows the reference to turn before
outward travel, and ramps speed to the existing cruise setting as forward
clearance permits. This is not a pose/velocity assignment to the physical
body, a neural motor decoder, or deletion of the safety stop.

`check_launch_clearance.py` is a **motor-only**, non-browser regression. The
center, reported-corner, north-facing outward corner and west-facing outward
edge cases each completed three seconds without floor contacts or a boundary
pause. Minimum boundary clearances were 43.48, 15.88, 15.17 and 15.17 mm;
minimum flight upright cosines were 0.6265, 0.6167, 0.4821 and 0.6224.
All handoffs preserved qpos/qvel. The results establish the tested launch
transition, not new biological or universal corner-recovery evidence.

External results: `results/fly-unified/launch-clearance-001`. This diagnostic
uses explicit ground initializations, not actual GF stimulation. The full
browser/neural regression remains separate and uses only port 8840.

The reduced DNp10 leg extension and continuous spherical-rate experiments
did not change flight direction. They therefore did not resolve this problem.
The new comparison is **not** a DN-count-to-turn mapping, does not choose
between ambiguous DNa04/DNa05 versus DNae004/DNae006 identities, and does not
invent a motor decoder for DNg02's bilateral amplitude response.

## Implementation

[fly_flight_avoidance.py](../scripts/fly_flight_avoidance.py) supplies a
deterministic receding-horizon reference to the existing FlyBody wing policy:

- Sample actual body position and five horizontal geometry rays every 10 ms.
- Retain at most 32 ray-detected geometry IDs. Update their physical centers
  and bounding radii from the model, so remembered obstacles cannot be
  repeatedly re-entered simply because they leave the current forward rays.
- Use **privileged arena bounds**, body pose and detected-object geometry,
  not calibrated retina or neural perception. Non-spherical shapes use
  conservative bounding spheres. Geometry more than its bounding radius
  plus 2 mm vertically from flight height does not block the horizontal plan.
- Evaluate candidate turn rates over a 1.2 s horizon, using measured body
  position and the current reference. Penalize predicted boundary/obstacle
  proximity and unnecessary/rapid direction changes.
- Bound yaw rate to 3 rad/s and yaw acceleration to 12 rad/s².
- Use a 20 cm/s, 1 cm-altitude flight reference, with a 0.2 s soft tracking
  correction limited to 5 cm/s. This adjusts only the synthetic policy
  reference; it never sets body position, velocity or physical joint state.
- Begin planning at GF-triggered launch and use the same curved reference
  during the existing 0.3 s **external launch assistance**. Leaving launch
  assistance straight while delaying turns consumed too much clearance.
- After launch assistance, turn only through the learned wing actions.
  No external steering force or torque is added.

There is no random wandering, pose wraparound, arena enlargement, teleport,
hidden restart or automatic landing. The reference is state-dependent, not
an unconditional fixed orbit, although sustained wall avoidance can produce
repeated curved circuits.

The original binary sensory encoder, sparse neural counts, reduced DNp10
option and model datasets remain available unchanged. The failed
`--engineered-navigation` landing-cycle experiments are separate and cannot
be combined with `--flight-avoidance`.

## Physical results

All data below are retained outside Git under `results/fly-unified`.

| Final-source trial | Initial heading / wing phase | Duration | Minimum arena clearance | Floor contacts | Outcome |
| --- | --- | ---: | ---: | ---: | --- |
| `avoidance-validation-long-001` | pi / 0.35 | 20 s | 16.27 mm | 0 | Pass |
| `avoidance-validation-diagonal-001` | pi/4 / 0.8 | 8 s | 17.59 mm | 0 | Pass |
| `avoidance-obstacle-005` | 0 / 0.5 | 8 s | 15.49 mm | 0 | Pass |
| `avoidance-obstacle-replay-001` | 0 / 0.5 | 8 s | 15.49 mm | 0 | Exact physical/action replay |
| `avoidance-browser-004` | Actual grounded GF launch | 5 s | 18.24 mm in flight | 0 in flight | Pass |

The raised obstacle test uses an explicit 10 mm-radius physical sphere at
70 mm forward and 10 mm height. Minimum thorax-to-obstacle surface clearance
was 3.98 mm, with zero obstacle contacts. The full qpos/qvel/action hash
matched its replay exactly. This is one bounded obstacle test, not universal
collision avoidance or dynamic-obstacle robustness.

The long trial physically traveled approximately **397 cm** within the
300 mm-wide arena, rather than remaining stationary while steering commands
changed. It maintained minimum height 9.70 mm and minimum upright cosine
0.6758. The obstacle run traveled approximately 160 cm.

The same-browser grounded trial preserved qpos/qvel at handoff, kept body
mass/inertia unchanged and completed **21,950** post-assistance flight steps
without floor contact or boundary pause. It used explicit upstream input
for the existing launch comparison; the separate physical-approach run below
did not inject that direct test input.

These are engineering thresholds, not empirical fly-matched behavior tests.
Distinct wing phases are actual physical initializations, not just different
neural seed labels. Twenty seconds of successful flight does not establish
indefinite stability.

### Retained failures and interactive trial

- `avoidance-001`: diagnostic setup failed before physical validation because
  the initial implementation called an unavailable task observation method.
  Initialization is now done before the environment produces observations.
- `avoidance-baseline-001`: straight-reference control reached the 5 mm
  boundary margin at 0.726 s. This is the preserved baseline failure.
- `avoidance-browser-001`: late turning after straight assisted launch still
  hit the safety boundary. The launch and flight references were made
  consistent, not reset.
- `avoidance-obstacle-001` and `-002`: ray-hit shifts delayed/cancelled the
  maneuver and produced obstacle contact.
- `avoidance-obstacle-003`: avoided the first pass but later contacted the
  obstacle after it left the forward rays. Bounded detected-geometry memory
  fixes that core omission.
- `avoidance-browser-003`: early obstacle memory treated low planted
  geometry as a flight-height threat and the reference drifted out of the
  arena. Height-aware planning and a bounded, measured-state reference
  correction were added. This failed bundle remains failed.
- `avoidance-approach-001`: an actual visible physical finger approach
  produced GF-triggered takeoff at 0.14 s and completed five seconds without
  boundary freeze or flight floor contacts. **The user edited the scene and
  toggled controls during this bounded run**, so it is an interactive result,
  not an untouched controlled comparison. Its inputs and failures/rejections
  are logged. The user's final removal of placed objects was preserved.

Failed landing trials `engineered-cycle-001` through `-007` are neither
overwritten nor relabeled as successful by this work.

Repository regression: **223 tests reported, seven environment/opt-in skips**.
Targeted tests check bounded turn/reference changes, measured-state-dependent
planning, invalid-clock rejection and explicit launcher options. Standalone
physical trials verify source hashes did not change while running.

## Same browser, one ongoing app

The selected live comparison is `interactive-app-008` at
**http://127.0.0.1:8840/**, started only after the bounded servers exited:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --flight-avoidance --neural-leg-extension \
  --scene experiments/fly-walking/planted-habitat.json \
  --feeding-config experiments/flywire-sugar/planted-feeding.json \
  --objects /latest/saved/objects.json \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/session
```

`--flight-avoidance` is explicit. The later approved
[compact grassland](grassland-habitat.md) supports half-size >=112.5 mm by
reducing the reference speed proportionally (15 cm/s at 112.5 mm; 20 cm/s
at 150 mm). Its obstacle rays also sample a three-level flight-height band.
The earlier 150 mm comparison and explicit straight-reference mode remain
available; the unified default scene is now the compact grassland.
The live session retains binary vision and does not enable failed landing,
graded sensory drive or automatic demo stimuli. Its motor label explicitly
identifies privileged engineered avoidance and learned wing control.
The latest edited placements were empty; earlier three-sphere files remain
available, but were not silently restored over the user's removals.

The emergency boundary stop is retained **for failures**, not used as the
normal turning mechanism. Flight recovery, landing and boundary handling
during walking remain separate incomplete behaviors. Camera/eye rendering,
environment editing and actual neural observation use the same app.

Organic flight still requires calibrated directional perception, descending/
VNC pathways and muscle recruitment that actually control wings. This
comparison fixes tested routine flight-boundary freezes; it does not close
those biological gaps.

Reproduce a physical trial:

```bash
MUJOCO_GL=egl .venv-flight/bin/python scripts/test_flight_avoidance.py \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/flight-trial \
  --seconds 20 --heading 3.14159265359 --phase 0.35
```

Use `--blocker --seconds 8` for the explicit obstacle test and `--disabled`
at heading zero for the straight-flight failure control.
