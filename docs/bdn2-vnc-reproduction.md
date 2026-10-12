# BDN2 nerve-cord circuit: bounded numerical validation

**Reviewed:** 2026-10-11. **Status:** putative rhythm-generator causality
supported in a published rate-model adaptation; strict archived-rate conformance
and motor alternation gates failed. No physical walking controller changed.

**Separate positive milestone:** the user-approved
[independent reference and single-joint proxy](independent-vnc-joint.md) now
passes numerical convergence/replay and isolated physical causal controls.
It does not supersede failed GPU comparisons or validate walking. Genuine
female-brain spike delivery, calibrated muscles and multi-leg coordination
remain separate gates.

## Latest continuation: actual masks and native solver

### Additional execution provenance found in archived logs

The archive also contains `run_hydra.log`, which was not included in the
earlier environment-metadata inspection. Its dated entries establish that
run28965859 executed on **2025-09-08 using four NVIDIA L40S GPUs**.
The CPU source snapshot used so far is dated2026-09-15; it is not established
as the exact code used in that earlier run.

Public Git history includes candidate execution-era commit
`edb18510c375dbf27e08644f172170e065c49022`, dated
2025-09-07T23:28:41Z, immediately preceding the logged run date.
There is no embedded commit identifier proving that this candidate was used.
Its reviewed rate equation, Dopri5/PID setup, output time-grid and tolerance
conventions match the corresponding later-source conventions; its environment
manifest requests unversioned `diffrax` and `jax[cuda12]`.

The archive log does **not** identify exact Python/JAX/JAXlib/Diffrax
versions or CUDA runtime/driver versions. No public tags/releases were returned
when checked. We now know GPU model/count and run date, but not the complete
execution environment. These findings narrow the reference search without
turning CPU mismatch into evidence of biological failure.

For filling remaining gaps, two goals must stay separate:

- A new explicitly specified, solver-converged computational reference can
  be established independently, with manifests, checksums, causal controls and
  held-out tests. It is a new baseline, not a relabeled match to the authors'
  archive; existing failed comparisons stay failed.
- Missing sensory/proprioceptive/muscle dynamics may be modeled as explicitly
  assumed surrogates and tested, but cannot be declared measured physiology.
  Physical controller changes require a bounded design and acceptance test,
  not an arbitrary spike-to-speed switch.

The earlier archived001/002 comparisons incorrectly treated
`*_mini_circuits.npz` as a connectivity mask. Pinned upstream code defines it
as **output activity above0.01**. The actual weight mask is
`neuron_params.h5/W_mask`. This was a local reproduction error and is now fixed,
with a regression test that preserves silent motor targets.
The old results below remain historical, not valid exact-mask reproductions.

For archived rows336/422/966, the actual weight masks retain **148 cells:
four core cells plus all144motor neurons**, not only the five active outputs.
The extra nonzero reference neuron in966 falls below the activity-mask threshold;
this is not by itself an inconsistent reference asset.

The user approved the separate CPU-only
[VNC environment](../experiments/fly-vnc/README.md). It pins JAX0.6.2,
Diffrax0.7.0 and supporting dependencies, within the advertised source
requirements. The original archive has no complete package/CUDA-version record; GPU models
and run date are now established from logs above. Environment equality is
not asserted. Existing brain/body
environments are unchanged.

Implemented the source float32 Dopri5/PID solver and exact gated input
(20ms through999ms), including the full4,604-state error norm. A dense-parent
operator diagnostic also checks against an equivalent projected calculation.
All cases require successful finite integration. The source's0..1000
postprocessing is explicit: raw minimum/maximum, clipped-sample counts and
solver steps are recorded. The first native001 run rejected a raw
-0.000189 rate; it remains failed. Later runs report finite negative numerical
samples before applying source clipping. Non-finite-to-zero fallbacks are never
used.

### Corrected-mask native results

`vnc-weight-mask-001` ran21causal/control cases. Core rhythms and disconnection,
no-input and exact-sham checks pass; **all three strict rate conformance checks
still fail** the unchanged0.05 bound:

| Archived row | Maximum core-rate difference, projected RHS | Dense-parent intact diagnostic |
| --- | ---: | ---: |
| 336 | 0.114113 | 0.113093 |
| 422 | 0.305598 | 0.249398 |
| 966 | 0.220305 | 0.284675 |

These are not tolerance/phase-window fits. No onset samples are discarded.
The dense diagnostic is `vnc-weight-mask-dense-001` and remains failed.
Earlier `vnc-native-002`/`vnc-native-dense-001` used the incorrect activity
mask and are not promoted as corrected-mask results.

The source solver and retained-state mistake are now explicit and addressed,
but CPU-versus-archived pointwise agreement is still unresolved. Different
historical solver versions and GPU-versus-CPU execution or discontinuity handling are possibilities,
not established explanations.

### Source-matched motor diagnostics

The complete144motor-target set was verified against archived `mn_idxs` and
the parent table. The core-plus-all-motor test at the first four saved
parameter rows retained genuine core oscillations, but did not pass the
unchanged coxa swing/stance antagonist gate. `vnc-all-motor-001` is retained
as failed; its protocol incorrectly listed core-conformance checks rather
than its motor checks. Protocol generation is corrected, and this old bundle
is not described as a successful preregistered motor validation.

To test whether omitting parent premotor pathways caused the failure, a
separate intact-only diagnostic used the **entire archived4,604-cell parent
connectivity**, saved parameters, source solver and unmodified250 input,
with rows0/1/2/3 fixed before execution. No new datasets or gains were added.
All four motor-output gates failed:

| Row | Coxa swing rate amplitude | Coxa stance rate amplitude | Swing/stance correlation |
| --- | ---: | ---: | ---: |
| 0 | 0.386552 | 0.005618 | 0.191669 |
| 1 | 0.495496 | 0.000426 | 0.434052 |
| 2 | 0.257058 | 0 | undefined |
| 3 | 0.327498 | 0.035524 | 0.336689 |

Evidence: `results/walking-paths/vnc-full-parent-001`. The declared motor gate
requires at least3prominent peaks in each averaged module, amplitude>1 and
correlation<-0.3. The above is a failed stronger engineering acceptance test,
not a claim that the paper's individual-MN rhythm finding was disproved.
This1s intact-only diagnostic supplies neither a whole-paper reproduction
nor a causal motor-control suite.

No muscle/actuator decoder is enabled. Next requires a trustworthy exact
reference execution and quantitative motor/proprioceptive transfer data,
not another guessed tonic drive or a more permissive gait threshold.

Latest validation: **266 tests run, eight skipped** in the existing flight
environment; **53 focused tests passed** in the isolated VNC environment,
including native solver tests unavailable in the flight environment.
Offline success does not overturn the scientific failures.

This advances the [walking initiation/stopping work](walking-neural-evidence.md)
beyond brain-side descending readouts without labeling a learned gait as neural
control or inventing a spike-to-speed gain.

## Selected primary model

Pugliese et al., [Connectome simulations identify a central pattern generator
circuit for fly walking](https://doi.org/10.1101/2025.09.12.675944) is a
**preprint**, not an established physiological whole-animal reconstruction.
Selected v1 results/discussion and public pinned code were reviewed. The
repository links v2; v2 fulltext requests returned HTTP429, so version identity
between the v1 narrative and latest code/data is not assumed.

The pinned [code/data snapshot](https://github.com/smpuglie/Pugliese_2026/tree/10e7661bf414ba7b4c2edf795cd36d0f878c17c0)
contains a reduced MANC network driven by DNg100/BDN2. Its first four cells are:

| Male MANC body ID | Reduced-table label | Function in the published model |
| --- | --- | --- |
| `10093` | BDN2 | Descending tonic input |
| `10707` | IN17A001 | Excitatory core interneuron |
| `11751` | IN15A001 | Excitatory core interneuron |
| `13905` | IN16B007 | Inhibitory core interneuron |

The parent table calls `11751` INXXX466 and `13905` IN16B036. Exact body IDs,
not label equality, bind the tables. Primary Sapkal Supplementary Table3
separately matches MANC BDN2 to the female brain BDN2 type; the IDs are not
interchangeable and no female brain/male nerve-cord graph is grafted here.
The inspected MANC DN matching table leaves matching-confidence fields empty
for BDN2/oDN1; no numeric confidence is invented.

The 123-cell reduced export has 119 motor neurons and 79 nonzero signed
chemical edges. Despite its T1L filename, the table contains 68 LHS cells
(including the four core cells) and 55 RHS motor neurons. Motor-to-motor edges
are preserved; motor-to-core feedback is absent. The core is:

```text
BDN2 -> E1: 187 signed contacts
E1 -> E2: 539; E1 -> I: 17
E2 -> E1: 19; E2 -> I: 71
I -> E1: -531; I -> E2: -172
```

These are topology/contact proxies, not measured conductances. Glutamate is
treated as inhibitory centrally by the published model; motor-cell predicted
transmitters and module annotations are not a verified muscle-force model.

## Dynamics and provenance

[test_bdn2_vnc.py](../scripts/test_bdn2_vnc.py) independently implements the
published rectified half-tanh **rate equation**, using the existing SciPy
environment. Source-to-target weights are transposed for target input and
multiplied by the published 0.03 factor. Gains and thresholds use the
published volume scaling; no feedback, pose-reset or muscle gain is added.

The original brain uses LIF spikes, whereas this VNC circuit uses continuous
rate states. A rate oscillator is not an exact synaptic-event reconstruction
and cannot be connected to the brain's BDN2 counts without an explicit,
validated transfer interface.

Only these user-selected assets were acquired using
[datasets.py](../scripts/datasets.py), outside Git:

| Asset | Bytes | Verified upstream checksum | Approved cap |
| --- | ---: | --- | ---: |
| Reduced MANC matrix | 121,160 | Git blob `0a978006660a8e8e0c0008af390ac0d730e4b9e7` | 200,000 |
| Reduced motor annotation table | 13,481 | Git blob `6f8dcdb6c96eedcb42226447db60a234fbf6c91d` | 200,000 |
| Parent 4,604-cell annotation reference | 671,375 | Git blob `071da7f6eeb4707c3ef899c30c79d09322782f7b` | 1,000,000 |
| Published DNg100 pruning archive | 274,050,687 | MD5 `6121b6992ac9cc685de72c0902ad55ea` | 300,000,000 |

The repository assets have no license declaration; local evaluation was
explicitly approved despite that uncertainty, not redistribution. The selected
[Zenodo record22260924](https://zenodo.org/records/22260924), published
2026-09-15, explicitly reports CC-BY-4.0 for its simulation archive.
Receipts bind source URLs, upstream checksums, sizes and local SHA256 values.
At this initial milestone, no new environment, JAX/Diffrax installation,
whole-connectome matrix or remaining release archive was acquired. The later
explicitly approved CPU environment is described above.

## Results, including retained failures

### 001: reduced-export normalization

The first numerical attempt used the reduced export's median volume. It did
not pass the motor alternation gate, and later hit a negative-rate numerical
check. All logs/results and failed status are retained. This was not promoted
as biological failure or published-model reproduction.

### 002/003: verified parent normalization and solver convergence

The parent reference has a median volume of **666,270,409**, and every reduced
cell's body ID/volume agrees with it. Parent-derived scaling is appropriate
for the published pruning setup.

002 retained another numerical negative-rate failure. 003 limited maximum
solver step to 0.1 ms and completed all 28 mean/sample control cases; no
negative/non-finite values were replaced with zeros. It used mean parameters
and NumPy truncated-normal samples at seeds420/421/427, not JAX seed parity.

Every intact case failed the declared motor-output requirement: each coxa
swing/stance module must have at least three peaks after300ms, rate amplitude
above1, and correlation below-0.3. Coxa stance remained silent. Tightening the
mean-case solver tolerance tenfold changed sampled rates by at most
**0.00005923**, below the declared0.05 convergence bound.

An absent rhythm in both intact and disconnected trials cannot establish
interneuron necessity. The runner now requires an oscillatory intact baseline
for that inference; earlier 003 control labels are retained but must not be
interpreted as a successful causal motor-rhythm result.

### Archived 001/002: actual author parameters and retained core outputs

The selected archive contains sampled arrays, topology, output-activity
masks and retained rates for run28965859. Initially we selected **all three**
activity masks with the four core cells and no active neurons outside the reduced export:
replicates336/422/966. Selection is based on topology containment, not local
performance. These are archived selected/pruned cases, **not prospective
independent validation**.

These historical attempts used saved arrays without resampling but incorrectly
used activity masks to remove connectivity; see the correction above.
The archived matrix differs
from the old reduced export at one motor-to-motor edge:
MANC27028 ->14346 is -6 in the archive versus +6 in the old export.
The corrected archived runner uses signed topology and actual HDF5 weight masks.

At1s with the saved250-model-unit drive from20ms to999ms:

| Archived replicate | E1/E2/I peaks after300ms | Maximum difference from archived core rates |
| --- | --- | ---: |
| 336 | 12 / 13 / 13 | 0.265908 |
| 422 | 13 / 13 / 13 | 0.162916 |
| 966 | 11 / 11 / 11 | 0.208728 |

**21/21 core-rhythm causal/control checks passed:** actual evolving network
rates oscillate; exact identity sham matches; no-drive and BDN2 output
disconnection are silent; cutting each of the three core output rows removes
the rhythm. No oscillator waveform is scripted.

**3/3 strict archived-rate conformance checks failed** the predeclared
0.05 absolute-rate bound. Differences are largest near stimulus onset
(22-23ms); the archived adaptive solver reports nonzero BDN2 rate at20ms,
where our explicitly segmented solver starts with zero state. This suggests a
stimulus-discontinuity/solver mismatch but is not proof of the entire cause.
No onset samples were omitted, tolerance relaxed, phase shift fitted or
reference values altered to obtain a pass.

Overall archived002 status remains **FAILED:21/24checks**, with core causality
supported separately. Coxa antagonist output still fails. Replicating a core
oscillator therefore does not authorize a physical leg controller.

External evidence lives under `results/walking-paths/vnc-reproduction-001`
through003 and `vnc-archived-001`/002. Archives, rate arrays, protocol/code
hashes, parameter provenance, statuses and failures are preserved.

## Reproduction commands

Inputs must already be acquired and receipt/checksum validated. Each output
directory must be new and outside Git:

```bash
.venv-flight/bin/python scripts/test_bdn2_vnc.py \
  --data-dir "${FLY_DATA_DIR:?Set verified external storage}" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/vnc-$(date +%Y%m%d-%H%M%S)"

.venv-flight/bin/python scripts/test_bdn2_vnc.py --archived-parameters \
  --data-dir "${FLY_DATA_DIR:?Set verified external storage}" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/vnc-archive-$(date +%Y%m%d-%H%M%S)"
```

These intentionally exit unsuccessfully when declared scientific gates fail;
they do not start a browser app or modify any motor controller.

## Remaining path to walking brain control

1. Establish exact solver/stimulus conformance with the archived baseline
   before claiming a published-model numerical reproduction.
2. Reproduce motor-module alternation with a source-matched parent circuit
   and the author's saved parameters. A three-interneuron core alone does
   not justify omitted motor excitation paths or artificially added tonic drive.
3. Identify and calibrate proprioceptive/contact feedback, motor-neuron-to-
   muscle activation, force/torque and joint-axis/units. This reduced network
   contains none of the required sensory receptor inputs.
4. Define a source-supported BDN2 spike-to-VNC interface. Brain LIF events
   and male VNC continuous rates must not be silently treated as equivalent.
5. Require genuine neural dependence, stable contacts, measured joint timing,
   effective silencing/sham/replay and held-out perturbations on one body.

Current walking remains a learned motor comparison. No arbitrary threshold,
spontaneous firing, energy-routing mechanism, periodic gait or muscle-force
mapping was introduced by this milestone.

Validation: **261 offline tests run, six skipped, no failures** in the existing
flight environment with EGL. Scientific failures above remain failures; passing
unit tests do not overturn them.
