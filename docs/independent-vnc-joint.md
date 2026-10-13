# Independent VNC reference and isolated joint interface

**Date:** 2026-10-11. **Status:** independent numerical reference and assumed
single-joint physical proxy validated under bounded controls.
**Not:** archived GPU parity, female-brain spike control, calibrated muscles,
reconstructed proprioceptors, free-body walking or an autonomous animal.

**Subsequent spike test:** [genuine brain packet relay](brain-spike-joint-test.md)
passed24neural controls but failed4of66coupled checks. It produces a bounded
motor-dependent response at prospective seed430, not robust control across
all tested seeds. This earlier rate-reference milestone remains distinct.

The user approved establishing our own computational reference and testing
explicit assumptions where physiological parameters are missing. This work
does not turn the retained [archive comparison failures](bdn2-vnc-reproduction.md)
into passes.

## Exactly what is connected

```text
prescribed250-model-unit tonic input
  -> measured signed male MANC BDN2/core/motor connectivity
  -> published assumed continuous rate dynamics
  -> exact motor body12686 rate output
  -> assumed recruitment and activation filter
  -> assumed local joint position/velocity feedback
  -> direct torque at one existing FlyBody hinge
```

| Surface | Data-backed component | Assumed or missing component |
| --- | --- | --- |
| Descending identity | Primary BDN2 type correspondence; MANC body10093 | No female FlyWire root is substituted for that male VNC ID |
| VNC topology | Archive signed connectivity and actual HDF5 weight mask; four core cells plus all144motor targets | Conductances, membrane physiology and input scale remain model assumptions |
| Neural dynamics | Independently tested numerical solution of the rate equation | Continuous rates, not individual brain LIF spikes |
| Motor target | MANC body12686, Tergopleural/Pleural promotor MN; annotated coxa swing | Its muscle geometry and force law are not reconstructed |
| Mechanical target | Existing `walker/coxa_T1_left` hinge, model axis `[1,0,0]` | One chosen joint proxy, not a verified fore-aft promotor mapping |
| Recruitment | Bounded activation computed from the real model output | Rate normalization,60ms filter and torque scale are declared assumptions |
| Feedback | Actual measured joint angle/velocity, resampled each physical step | Local corrective torque, not reconstructed sensory neurons or feedback into the VNC graph |
| Mechanics | Actual FlyBody MuJoCo dynamics; original masses/inertias preserved | Thorax externally welded in a raised bench; all other actuators disabled |

The FlyWire brain worker, its inputs/spike baseline, normal gait, flight and
interactive launcher are unchanged. No periodic motion waveform, joint pose
reset during stepping or hidden neural firing is introduced.

## Independent numerical reference

[vnc_reference.py](../scripts/vnc_reference.py) reuses already acquired,
checksum/receipt-verified assets. It uses the actual archive matrix and retained
core-plus-motor set, preserving male body IDs and signed motor-to-motor edges.
No new dataset, license bypass or environment installation occurred in this
milestone.

This is a **new baseline**, not a comparison against historical GPU rates:

- Float64 arithmetic with explicit stimulus boundaries at50ms and800ms.
- One-second duration,1ms output grid.
- RK45, relative tolerance2e-9, absolute tolerance5e-12, maximum step0.2ms.
- Full148-cell comparison against independent DOP853 and tenfold tighter RK45.
- No clipping or non-finite-to-zero fallback in the reference.
- Exact sham and fresh reset replay; silent no-input; descending output
  disconnection; motor-state clamp while upstream activity remains.
- Archived parameter rows336/422 for development, and new NumPy parameter
  seed428. A second run froze seed429 before inspecting its output.

Both `own-reference-001` and `own-reference-002` pass **33/33 checks**.
These include independent-integrator/tighter-tolerance agreement at every
neuron/time sample within the declared0.001 rate-unit bound:

| Parameter variant | RK45 vs DOP853 maximum difference | RK45 vs tighter RK45 |
| --- | ---: | ---: |
| saved336 | 0.000001675 | 0.000001524 |
| saved422 | 0.000005447 | 0.000004168 |
| new seed428 | 0.000020651 | 0.000019681 |
| new seed429 | 0.000070257 | 0.000071073 |

Reset/sham differences are exactly zero. No-input and motor-clamp motor output
are exactly zero. A descending cut preserves driven BDN2 activity while
eliminating interneuron/motor activity.
Interneuron-cut traces are retained, but a finite trace is not described as
proof of whole-gait necessity or successful antagonist recruitment.

The canonical raw motor trace for saved336 contains one interpolation sample
at -2.483175e-9, within the reference's declared -1e-8 numerical bound.
The raw array is preserved. The physical interface explicitly reports and
projects only accepted negatives in[-1e-8,0) to zero; larger negatives and
non-finite values fail. This projection is not hidden physiological activity
or a replacement for failed numerical results.

## Assumed single-joint physical proxy

[test_vnc_joint.py](../scripts/test_vnc_joint.py) requires a passed reference
with all33 expected checks, exact body-ID ordering, exact sample clocks and
unchanged full-array hashes. Empty/duplicated control results, bad convergence,
changed motor identity and changed rate arrays cannot authorize the probe.

The raised, welded bench retains FlyBody masses/inertias and passive joint
mechanics. It converts only the chosen existing actuator to a bounded direct
torque channel and zeros every other actuator gain/bias. It does not use a
trained walking policy, force the body to move forward or disable gravity.
The weld is external fixture assistance and is disclosed as such.

### Fixed model assumptions

```text
recruitment = motor_rate / (motor_rate +10)
activation relaxation time =0.06s
feedforward torque =0.002 * activation
local feedback torque = -0.005*(joint_angle-initial_angle)
                        -0.00005*joint_velocity
combined torque bounded to +/-0.002
```

Lengths use cm, angles rad and torques **g*cm^2/s^2**, consistent with FlyBody.
The rate constant10 is in model-rate units, not an experimentally fitted
motor response. The chosen joint/axis, passive-mechanics probe, torque gain,
activation filter and local feedback are assumptions, not a calibrated
neuromuscular reconstruction.

Rate samples are left-held causally: a sample at a numerical clock boundary
affects subsequent physical steps. There are no invented spike timestamps.
Local feedback changes the torque command, not the precomputed neural trace.

### Controlled physical results

Each run uses three parameter variants and eight cases:
intact, sham, DNcut, MNsilence, no-input, motor-disconnected, feedback-cut and
fresh-reset replay. Final `joint-proxy-005` uses saved336/saved422 and the
fresh seed429 reference: **24 trials,24/24 checks passed**.

| Variant | Maximum intact-minus-no-input joint difference | Feedback-cut minus intact maximum difference |
| --- | ---: | ---: |
| saved336 | 0.011640rad | 0.008119rad |
| saved422 | 0.010786rad | 0.007941rad |
| new seed429 | 0.022077rad | 0.010283rad |

- Sham/reset qpos, qvel, actuator commands and actuator-force hashes match
  exactly.
- Descending cut, motor-state silence and physical motor disconnection all
  match the no-input physical trajectory exactly.
- Feedback removal has exactly zero added feedback torque and changes joint
  motion beyond the declared0.0001rad bound.
- Maximum fixture drift is0.001060cm, below the unchanged0.01cm limit.
- Maximum torque is0.0005515g*cm^2/s^2, below the0.002 limit; source joint limits
  are respected.
- No additional `xfrc_applied` or `qfrc_applied` forces are used. This does
  not erase the externally imposed weld reaction.

No-input physics is **not frozen**: gravity/passive mechanics produce a final
angle around0.027372rad. The above response is paired relative to that actual
baseline, not a claim that every observed degree of motion is neural.

### Retained failures and refinements

- `joint-proxy-001` rejected the small negative interpolation sample. It remains
  failed; explicit bounded roundoff reporting/projection was then added.
- `joint-proxy-002` completed the neural controls but failed all three fixture
  bounds: weld drift0.013264cm exceeded0.01cm.
- Only the external fixture time constant changed from2ms to0.5ms.
  Recruitment, neural dynamics, torque/feedback gains and scientific bounds
  did not change. `joint-proxy-003` then passed.
- Fresh seed429 was generated and numerically validated after that fixture
  correction; `joint-proxy-004` passed its physical controls.
- `joint-proxy-005` adds strict manifest validation and explicit torque units;
  all24 physical hashes are exactly equal to004.

All failed bundles, protocols, raw reference arrays and full physical interval
logs remain outside Git under `results/walking-paths/`.

## Reproduction

Use the existing isolated numerical and physical environments. Inputs must
already be explicitly acquired; outputs must be new and outside Git:

```bash
: "${FLY_DATA_DIR:?Set verified external storage}"
REFERENCE_DIR="$FLY_DATA_DIR/results/walking-paths/reference-$(date +%Y%m%d-%H%M%S)"
.venv-vnc/bin/python scripts/vnc_reference.py \
  --data-dir "$FLY_DATA_DIR" --output-dir "$REFERENCE_DIR" --parameter-seed 429

MUJOCO_GL=egl .venv-flight-py311/bin/python scripts/test_vnc_joint.py \
  --reference-dir "$REFERENCE_DIR" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/joint-$(date +%Y%m%d-%H%M%S)"
```

Overwriting an existing output is rejected. These research runners do not
launch a browser app or change normal habitat behavior.

## Next gate

This closes the independent numerical-reference gap and demonstrates a
single rate-model-driven joint interface under causal controls. It does
**not** close the brain-spike, muscle anatomy, calibrated feedback, multi-leg
coordination or spontaneous-initiation gaps.

Next: deliver genuine FlyWire BDN2 spike-count packets through an explicitly
declared spike-to-VNC interface into this same isolated bench, with source
silencing, replay and delivery-clock controls. Only then consider expanding
to a coordinated leg or gait; do not replace the missing interfaces with an
always-walking policy and call it neural.

That next packet test has now been executed and its mixed results are linked
above; its assumed current transfer is not validated for general deployment.

Validation: **274 offline tests run, eight skipped, no failures** in the
existing flight environment, plus numerical/native tests in the VNC environment.
These tests validate implementation; they do not establish biological fidelity.
