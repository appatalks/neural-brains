# Continuous spherical vision and the reduced DNp10 motor loop

This approved increment replaces the binary 100 Hz looming gate **only in an
explicit opt-in experiment** with continuously geometry-dependent input rates.
It keeps the actual FlyWire630 network, the previously validated reduced DNp10
leg decoder and articulated FlyBody physics. It is not calibrated retinal
vision, reconstructed VNC physiology, natural navigation or complete landing.

## Evidence versus assumptions

[Ache et al. 2019](https://doi.org/10.1016/j.cub.2019.01.079) supports the
feature distinction of LC4 angular-velocity and LPLC2 angular-size contributions
to GF escape responses. This is evidence for the selected features, **not**
the numerical rate curves below and not the natural DNp10 landing pathway.
The landing evidence instead identifies LPLC3/LPLC4-associated anatomy;
we do not relabel LC4/LPLC2 propagation as a verified natural landing circuit.

[fly_looming.py](../scripts/fly_looming.py) declares the assumed rate encoder:

```text
theta = physical sphere angular diameter, radians
v = positive angular expansion velocity, radians/second

LC4_Hz   = 100 * v / (v + 0.1)
LPLC2_Hz = 100 * theta / (theta + 0.05) * v / (v + 0.05)
```

Hidden, disabled, stationary or receding sources contribute zero. Each source
has a separate history in each eye; its first visible sample has zero expansion
velocity, so appearance is not treated as an invented movement. Occlusion,
removal/replacement, finger toggles and explicit Reset invalidate relevant
histories. Pause does not advance them.

Rates are pooled by the maximum per population across visible spheres/eyes.
This is a declared bounded reduction, not measured retinotopy, hemisphere
mapping or integration across receptive fields. The 100 Hz ceiling follows
the existing computational input comparison, not a biological maximum.
The half-saturation constants and positive-expansion gain are assumptions.
The reduced VNC/activation parameters remain unchanged.

## End-to-end implementation

```text
physical body/eye pose + sphere geometry and ray occlusion
 -> continuously varying LC4/LPLC2 input rates
 -> actual verified Poisson input populations and chemical FlyWire network
 -> exact DNp10 spike-count intervals
 -> explicitly reduced VNC/activation surrogate
 -> named FlyBody tibia position actuators and physical actuator forces
 -> physical joint/body motion
 -> next geometry sample and new sensory rates
```

Each neural interval is 10 ms. The rates are constant within that interval;
this is not continuous-time retinal simulation. Actual DN counts arrive at
the interval boundary and can influence only subsequent physics.

[fly_brain_worker.py](../scripts/fly_brain_worker.py) keeps the existing shared
PoissonGroup and neuron order. It assigns independent LC4 and LPLC2 rate values
to their exact version-matched input indices; it does not merge populations,
inject DN spikes or change the chemical topology.

[fly_feeding.py](../scripts/fly_feeding.py) validates a strict finite
`visual_rates_Hz` object with exactly `LC4` and `LPLC2`, each in [0, 100] Hz.
The worker echoes the applied rates and the client checks them before accepting
activity. Missing/malformed inputs fail explicitly. Binary workers reject rate
inputs; graded workers require them. The old binary interface remains the
default and its original causal protocols remain available.

## Physical feedback controls

[test_graded_visual_feedback.py](../scripts/test_graded_visual_feedback.py)
reuses the existing physical two-presentation leg-extension assay:

- Reference and variant sphere geometries, actual eye pose and occlusion.
- Actual full-network workers and an explicit airborne physical initialization.
- Unchanged wing policy, wing phase 0.5, no external body assistance or
  within-trial pose/velocity resets.
- Intact, scheduled identity sham, visual-source chemical-output disconnection,
  DNp10 voltage-clamp spike silencing, motor-interface disconnection,
  no-input, receding and exact reset replay.
- **Feedback cut:** remove neural drive only during the second physical
  presentation, preserving the initial sensory/neural/motor chain.
- **Feedback sham:** replay the intact rate trace exactly.
- **Feedback clamp:** replay rates from the motor-disconnected physical
  control into an otherwise actuator-connected trial. This isolates the tiny
  motor-dependent change in geometry/rates from the large second presentation.

The assay checks real neural and physical differences, not just decoder
activation or graphics. It retains the original >=0.15 rad front-tibia and
>=0.1 mm forward-claw paired thresholds, and requires a >=0.01 rad physical
response difference after the second presentation starts when that input is
cut. This measurement window includes neural and actuator delay, not only
the time while the stimulus is visible. These remain model/engineering
thresholds, not empirical fly tolerances.

Source hashes are verified before/after workers and at completion; changed
source files stop final validation explicitly. Data/results remain outside Git.

### Measured results

External `results/flight-steering/graded-feedback-002` passed **100/100 checks
across 44 trials**, with source hashes unchanged. Seed 423 was not used to set
the encoder or motor parameters.

| Neural seed | Geometry | DNp10 spikes | Peak mean front tibia change (rad) | Peak mean forward claw change (mm) |
| --- | --- | ---: | ---: | ---: |
| 420 | Reference | 4 | 0.2844 | 0.1901 |
| 420 | Variant | 3 | 0.2662 | 0.1769 |
| 423 | Reference | 4 | 0.2553 | 0.1690 |
| 423 | Variant | 2 | 0.1880 | 0.1214 |

Joint/tip changes are measured against motor-disconnected physical controls.
Source disconnection, DN silencing, no-input and receding controls eliminated
DN recruitment. Intact, scheduled sham, exact sensory-rate replay sham and
paired reset matched neural/physical hashes.

Cutting the second presentation reduced its network response from
5,055–5,219 spikes to zero and reduced total DNp10 responses from 2–4 to 1–2.
It changed the subsequent mean front-tibia trajectory by 0.1727–0.2730 rad,
while leaving the initial stimulus/neural/motor chain unchanged.

Motor-dependent geometry changed encoded input rates by approximately
0.00070–0.00209 Hz. Replaying the motor-disconnected rates into the otherwise
intact actuator trial produced **exactly the same neural and physical hashes**
as intact in all four seed/geometry comparisons. Thus the encoder transmits
the geometric feedback difference, but those small changes did **not** alter
spikes or motion within these trials. Feedback stabilization remains unproven.

`graded-feedback-001` is retained as the initial integration run, not a frozen
source release: source validation/history handling and stricter assay checks
were developed while it ran. Its provenance audit explicitly records that
limitation. Final results above come from the subsequent unchanged-source run.

`results/flight-steering/graded-parity-001` establishes exact maximum-rate
parity with the original binary input: **58,750 network spikes** at seed 420,
identical sparse/candidate/GF outputs, exact reset replay and silent zero-input
control. The exact visual input populations contain 104 LC4 and 210 LPLC2
neurons; no IDs or populations were merged. Separate population drive is tested.

Repository regression validation reported 219 tests with seven environment/
opt-in skips. The explicit legacy actual-network activity suite passed all ten
tests; graded full-network parity and compiled-geometry/occlusion tests also
passed.

### Important feedback limitation

Continuously varying **rates** need not produce different finite-duration
Poisson **spikes** for tiny changes. The feedback clamp reports exact neural
and physical hash equality/inequality rather than forcing a success label.
Removing a whole second presentation can affect spikes and motion even if
the much smaller motor-dependent rate change cannot.

This distinction prevents a positive sensory-to-motor experiment from being
misrepresented as closed-loop neural stabilization. Proprioception, full
optic flow, natural landing encoding, real VNC/muscle recruitment, stable
touchdown and unassisted walking recovery remain unresolved.

## Same app, one live instance

The unified launcher/app adds `--graded-vision`, default off:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --graded-vision --neural-leg-extension \
  --scene experiments/fly-walking/planted-habitat.json \
  --feeding-config experiments/flywire-sugar/planted-feeding.json \
  --objects /previous/session/objects.json \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/session
```

The single app normally uses port 8840. Occupied ports fail explicitly; there
is no automatic second-port/version fallback. Bounded experiments run
sequentially before the live session is launched.

Unlike the old finger-only encoder, graded vision samples actual saved **sphere**
placements and the habitat's spherical flower center as well as the finger.
Leaves, boxes and ellipsoids can occlude these sources, but their own silhouettes
are not encoded. Light/odor markers are not substituted for sensory neurons.
This limited spatial scope is visible in the existing browser status.

The rate values displayed in the app are **assumed input drive**, not measured
LC4/LPLC2 firing. DNp10 and other neural readouts still come from actual spikes.
Flight initiation remains actual GF-triggered assistance; wing/walking control
remains learned. Leg extension is not landing.

The old `interactive-app-005` was explicitly saved/stopped at the user's request.
Its three edited sphere placements and failed landing bundles were preserved;
the old result directory was not deleted. The obsolete port-8841 test page
is not another running simulation.

### Browser validation and live deployment decision

`results/fly-unified/graded-browser-test-001` completed a 1.2 s same-app
experiment with explicit upstream input only for the established launch
comparison, then a physical sphere during flight. It recorded three flight
DNp10 spikes, peak applied activation 0.5148 and 2,950 post-assistance flight
steps without floor contacts. Handoff qpos/qvel and body mass/inertia were
preserved. The engineered launch assistance remains disclosed.

The subsequent graded live session, `interactive-app-006`, sampled the three
saved spheres without a demo stimulus. It recorded 1,638 network spikes and
12 GF spikes, triggering assisted takeoff and reaching the existing flight
boundary safety pause at **0.75 s**. DNp10 remained silent. This is a retained
live-use limitation: the assumed encoder/GF model is not calibrated to
distinguish everyday scene expansion from an appropriate escape response.
It is not successful live navigation or leg-extension evidence.

After this outcome was reported, the user selected the preserved **binary**
encoder plus the validated reduced DNp10 leg option for the sole live app.
The graded session was saved/stopped before `interactive-app-007` was launched
on port 8840 with the same three saved spheres. Sugar enabled, slippery ground
and camera-follow-off settings were restored through logged environment
controls. No second app/port was left running.

World/eye images and the reduced-neural scope labels were verified in the
browser. The user subsequently enabled the finger: the live log records actual
GF responses with looming input, not an automatic test stimulus. The existing
straight-reference flight later safety-paused; it was not secretly reset.
The boundary/landing/navigation limitation still applies to this comparison.

Reproduce final causal validation in a new external directory:

```bash
MUJOCO_GL=egl .venv-flight-py311/bin/python scripts/test_graded_visual_feedback.py \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/graded-feedback \
  --seeds 420 423
```
