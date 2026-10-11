# DNp10-driven physical leg extension: reduced model

This opt-in increment connects **actual FlyWire630 DNp10 spikes** to physical
FlyBody leg motion. It is not complete landing, a reconstructed VNC circuit,
or calibrated muscle physiology. Walking and wing control remain the published
learned comparisons. The baseline and failed landing experiments are preserved.

## Evidence and missing interfaces

[Ache et al. 2019](https://doi.org/10.1038/s41593-019-0413-4) causally associates
DNp10 and DNp07 activation with landing-like extension of all six legs. Its
experiments include tethered flies, and the front legs can reach beyond the
head. These are not free-flight touchdown measurements.

The verified female FlyWire630 DNp10 pair is:

| Side | FlyWire root ID | Separately matched male MANC body ID |
| --- | --- | --- |
| Left | 720575940620153765 | 10835 |
| Right | 720575940619678366 | 10732 |

MANC's DNxl018 type match is anatomical evidence, **not neuron-ID equality**.
The reduced model does not graft male VNC IDs onto female brain connectivity.
It does not choose between the ambiguous DNa04/DNa05 and DNae004/DNae006 pairs.
DNp07 remains observational: its octopamine-dependent response is not modeled.

| Interface | Available evidence | Implementation / remaining gap |
| --- | --- | --- |
| World -> sensory input | Physical eye pose, silhouette geometry and ray visibility | Existing binary LC4/LPLC2 Poisson gate, sampled every 10 ms; not a fitted landing encoder |
| Sensory input -> DNp10 | Actual loaded chemical network and exact verified DN counts | Implemented model propagation; does not establish the natural LPLC3/LPLC4 landing pathway or calibrated DN responses |
| DNp10 -> VNC recruitment | Type-level VNC correspondence and causal leg-extension phenotype | New **assumed reduced bilateral recruitment**, not measured motor-neuron connectivity/dynamics |
| Recruitment -> muscle/effectors | FlyBody named joints and position-actuator mechanics | New assumed activation-to-tibia-target mapping; actual muscles, recruitment and force law remain missing |
| Effectors -> physics | Existing articulated FlyBody dynamics and actuator forces | Actual actuator-driven motion; no body pose/velocity resets or external extension assistance |
| Physics -> sensory feedback | Updated physical camera pose and visible sphere geometry | Resampled before every neural interval; coarse gate still limits feedback resolution |
| Extension -> touchdown/walking | Failed engineered-cycle evidence | Still unresolved; extension is not deceleration, wing shutdown, stable contact or walking recovery |

## Explicit assumptions

[fly_leg_extension.py](../scripts/fly_leg_extension.py) verifies the exact pair,
receives exact sparse-checked counts, and updates a bounded activation:

```text
a_boundary = 1 - (1 - a_previous) * exp(-0.35 * combined_DNp10_count)
a(t + dt) = a(t) * exp(-dt / 0.08 seconds)
tibia_target = existing_flight_target + 0.9 radians * a
```

The 0.35 recruitment, 80 ms decay and 0.9 radian excursion are **declared
model assumptions**, not measured physiology or fitted connectomic weights.
Both DN copies recruit the same six tibia channels. This symmetric reduction
does not claim measured side-specific VNC anatomy. Targets are name-mapped and
clipped to the existing actuator limits.

The FlyBody leg position actuators already have a 10 ms control filter. Neither
this filter nor the reduced activation is a biological muscle model. Generalized
actuator forces are logged in native FlyBody units, not relabeled muscle forces.

Counts become available at the **end** of a neural interval. Recruitment affects
only subsequent physical steps: no invented within-interval spike times or
retroactive movement. No-input activation is exactly zero; withdrawal decays
existing activation rather than forcibly resetting it.

Actuation is restricted to the comparison backend's `flight` phase. This is
an explicit scope/safety choice, not a fitted DNp10 flight-state/octopamine gate.
Walking and assisted takeoff keep their original controllers.

## Causal assay

[test_leg_extension_causality.py](../scripts/test_leg_extension_causality.py)
uses the actual persistent full brain in a separate pinned worker. Each physical
trial explicitly starts airborne, holds the published wing policy unchanged,
and runs without external body assistance. Reset is only between trials.

Cases: intact, scheduled identity sham, LC4+LPLC2 chemical-output disconnection,
DNp10 model spike silencing, motor-interface disconnection, no object, receding
object, and exact paired reset replay. Spike silencing clamps the selected DN
voltage/synaptic state before threshold evaluation; it is not claimed equivalent
to an animal silencing method. Source-output disconnection retains source spikes.

The final two-presentation protocol uses reference and offset/radius-variant
physical spheres. A second collision-free world-space presentation tests visible
feedback after recruitment. Objects are explicit environmental interventions,
not body resets. The trial lasts 0.7 s; seed 422 is prospective validation after
the earlier seed-421 failures. Decoder parameters are unchanged across trials.

Predeclared checks include:

- Intact/sham/reset neural and complete physical/action hashes match exactly.
- Visual disconnection and DN spike silencing eliminate recruitment.
- Motor disconnection preserves DN responses but eliminates decoded movement.
- Mean front tibia excursion >=0.15 rad and forward claw displacement >=0.1 mm
  relative to the motor-disconnected physical control.
- Actual generalized actuator force changes; visible post-actuation angular
  geometry changes relative to that control; the feedback presentation reaches
  the brain through the existing encoder.
- No floor/sphere contacts, nonfinite physics, body resets or external assistance;
  minimum upright cosine >0.4.
- Final activation <=10% of peak after withdrawal.

These are engineering/model thresholds, not empirical fly tolerances. The
forward claw displacement test does **not** establish the paper's complete
front-leg-reaching-beyond-head phenotype. A changed geometric sample does not,
by itself, prove changed spike patterns: the binary encoder can quantize away
small physical-feedback differences.

The later approved [continuous spherical-vision increment](graded-visual-feedback.md)
removes the binary rate quantization in an opt-in comparison and adds explicit
sensory replay/cut controls. It does not change the reduced motor parameters
or resolve the missing biological VNC/muscle model.

### Final measured results

`results/flight-steering/dnp10-extension-004` passed **102/102 checks across
48 trials**, including prospective seed 422. All model parameters remained
unchanged; only the disclosed assay presentation schedule evolved.

| Neural seed | Geometry | DNp10 spikes | Peak mean front tibia change (rad) | Peak mean forward claw change (mm) |
| --- | --- | ---: | ---: | ---: |
| 420 | Reference | 3 | 0.2662 | 0.1768 |
| 420 | Variant | 3 | 0.2662 | 0.1768 |
| 421 | Reference | 2 | 0.1841 | 0.1188 |
| 421 | Variant | 3 | 0.2635 | 0.1749 |
| 422 | Reference | 4 | 0.3526 | 0.2407 |
| 422 | Variant | 5 | 0.3131 | 0.2112 |

These are paired differences from the motor-disconnected control, not absolute
joint angles. Visual disconnection, DN silencing, no-input and receding cases
all had zero DN recruitment. Intact/sham/reset hashes matched exactly.
Motor disconnection retained DN activity and matched DN-silenced physical
trajectories. All trials had zero floor/sphere-contact steps and no external
assistance; minimum upright cosine was 0.6674.

Visible angular feedback differences were small: approximately
3.2e-7 to 3.26e-5 rad. The second presentation reached the brain via the
geometric gate, but these results do **not** demonstrate physiological feedback
stabilization or changes in neural spike patterns caused by those small
differences. Leg proprioception is not encoded. This distinction remains a
blocker, not a new completed-behavior claim.

The tested body initialization uses one explicit wing phase, 0.5. Neural seeds
are not different physical wing phases. Broader phase, perturbation, empirical
timing/pose and muscle-force tests remain unpassed.

### Preserved earlier results

External bundles under `results/flight-steering`:

- `dnp10-extension-001`: short-pulse seed-420 reference and variant causal
  checks passed; peak mean front tibia change 0.1756 rad and forward claw
  displacement 0.1129 mm. This earlier assay did not require visible feedback.
- `dnp10-extension-002`: failed. Seed 421's short variant produced **zero
  DNp10 spikes and zero recruitment**. Its evaluator also encountered a
  missing-latency error, now covered by a regression test. Per-trial files
  preserve the silent result; no fake response was substituted.
- `dnp10-extension-003`: both seeds passed the neural/motor intervention and
  physical-extension checks, but seed 421 failed the strict visible-feedback
  checks because its response arrived after withdrawal. The overall run
  remains failed. Seed 420 measured 0.2662 rad / 0.1768 mm; seed 421 measured
  about 0.1756 rad / 0.1130 mm.

## Same-browser integration

The original port-8840 session was not stopped, reset or replaced.
The new behavior is off by default. To enable it in a **new approved** session:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --neural-leg-extension \
  --scene experiments/fly-walking/planted-habitat.json \
  --feeding-config experiments/flywire-sugar/planted-feeding.json \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/session
```

Preserve saved placements with `--objects /previous/session/objects.json`.
Do not start this on an occupied port or replace a live user session without
approval. Engineered assisted landing and reduced neural extension are mutually
exclusive experiments.

The existing browser motor status labels the actual DNp10-to-surrogate pathway,
activation, flight-only actuation and absence of calibrated muscles/touchdown.
Pause does not replay counts or advance activation; explicit paired Reset clears
both neural and reduced-model state.

An isolated 1.2 s integration run, `results/fly-unified/dnp10-browser-001`,
used explicit upstream stimulation **only to initiate the existing assisted
takeoff**, then a stationary physical approaching sphere during flight.
It recorded two additional flight DNp10 spikes and peak applied activation
0.3813. Compared with `dnp10-browser-baseline-001` under the identical test
schedule, peak mean front tibia change was 0.2457 rad. Both preserved takeoff
qpos/qvel and mass/inertia, and had 2,950 flight steps without floor contacts.
Takeoff assistance remains disclosed; extension does not add body assistance.

`dnp10-browser-visual-001` verified the same opt-in app at a separate temporary
test port: actual world and eye images loaded (1280 px and 512 px widths),
the reduced-model labels/activation were visible, and there was no horizontal
overflow. These test servers exited after their bounded runs.

The final-code repeat, `dnp10-browser-002`, retained the same two flight DN
spikes and peak activation. Its summary explicitly distinguishes
`neural_motor_decoding: true` for the **reduced** pathway from
`calibrated_vnc_muscle_decoding: false` and `landing_validated: false`.
No all-biological interpretation is implied by the first field.

Regression validation: 208 repository tests reported with six environment/
opt-in skips; the explicit actual-network activity/parity suite separately
passed all ten tests.

Reproduce the physical controls in a new external directory:

```bash
MUJOCO_GL=egl .venv-flight/bin/python scripts/test_leg_extension_causality.py \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/causal-assay \
  --seeds 420 421 422
```

This increment is a functional, connectome-informed **reduced actuator
comparison**, not a claim of complete biological landing or a completed fly.
