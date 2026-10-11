# Neural landing: what is established and what is missing

The user prioritizes evidence-based neural steering/landing. A subsequently
approved [DNp10-driven reduced leg-extension model](neural-leg-extension.md)
now supplies an opt-in physical actuator comparison with explicit assumptions
and causal controls. It is not a reconstructed VNC/muscle circuit or touchdown.
The baseline browser still uses learned reference flight and an explicit
boundary safety pause; this document does not claim completed landing.

The later user-selected [brain-linked reduced landing model](brain-linked-landing.md)
now requires actual DNp10 spikes to initiate an explicitly assisted
brake/descent/wing-to-leg transition. Physical contact, zero-assistance walking
and neural silencing controls have bounded model evidence. This is not a
reconstructed natural landing pathway or calibrated muscle model; the primary
biology/identity limits below still apply.

## Primary causal evidence

[Ache et al., Nature Neuroscience 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC7444277/)
identifies DNp07 and DNp10 as causal drivers of visually evoked **landing leg
extension**. Type-specific activation evokes extensions; silencing reduces
their response to frontal looming or unilateral front-to-back bars.
Recordings show spiking precedes leg movement.

The experiments include tethered/head-fixed flies. Recorded leg extension
is not equivalent to decelerating a freely flying body, making stable ground
contact, stopping wing power, and resuming walking.

Flight-state dependence is essential. DNp07's visual response is gated by
octopamine; DNp10's response is not similarly increased by octopamine bath
application. Applying the same binary flight-state gain to both would erase
a measured difference. The current homogeneous LIF model does not implement
these verified neuromodulatory/state pathways.

Stimulus methods include frontal looming r/v = 80 ms and unilateral
front-to-back bars at 500 degrees/s. These protocol values are not a complete
rate encoder, circuit parameter fit, or spike-to-muscle force law.

## Version-matched identity and contact audit

[audit_sensorimotor_paths.py](../scripts/audit_sensorimotor_paths.py) verifies
the historical FlyWire630 annotation/model assets. The landing names occur
in `hemibrain_type`, with an empty `cell_type`, so searching only the latter
would wrongly report absence.

| Candidate | Side | Verified root ID | Incoming neurons | Incoming contacts |
| --- | --- | --- | ---: | ---: |
| DNp07 | Left | 720575940617034565 | 557 | 4,658 |
| DNp07 | Right | 720575940622550089 | 493 | 4,068 |
| DNp10 | Left | 720575940620153765 | 924 | 7,672 |
| DNp10 | Right | 720575940619678366 | 455 | 1,871 |

All are present in the loaded 127,400-neuron network. IDs remain strings,
and the audit preserves annotated upstream partners/contact counts.
These are brain-side chemical connections, not VNC muscle-target identities
or conductance measurements.

The acquired primary MANC DN matching table identifies DNp07 as DNxn027
(body IDs 11228 left / 11150 right), and DNp10 as DNxl018
(10835 left / 10732 right). Both receive published light-level matching
confidence 5/5. These are **male VNC body IDs**, not replacements for the
female FlyWire root IDs above. The matching audit preserves both namespaces.

## MANC does not close the motor gap automatically

[Cheong et al.'s primary MANC circuit analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC13384506/)
provides relevant descending-to-motor anatomy. However, this is a separate
male nerve-cord specimen. Its cell/group IDs cannot be merged directly with
the female FlyWire brain's root IDs.

For steering, w-cHIN electrical connectivity is partly putative membrane
contact evidence. For landing, the necessary graded motor recruitment and
whole-body transition remain distinct from the observed leg response.

## Requirements for biologically calibrated landing

1. Resolve experimental driver/type correspondence and cross-specimen
   anatomy without claiming neuron-ID equality.
2. Fit visual/state-dependent DN responses from accessible quantitative
   recordings, with held-out stimulus and silencing tests.
3. Obtain justified VNC transmission, muscle recruitment and force/activation
   parameters; do not turn chemical counts or membrane contact areas into
   guessed electrical conductances.
4. Validate leg-extension timing first, then separate deceleration, wing
   shutdown, contact stability and post-landing walking.
5. Compare causal neural interventions with sham/no-stimulus controls.

The reviewed assets do **not** supply a complete calibrated model for these
requirements. The user later approved an explicitly assumed reduced DNp10
VNC/activation-to-leg-actuator increment, rather than waiting indefinitely for
complete physiology. Its assumed gains are not described as measured, and
its causal model/physical tests are separate from biological calibration.
Neural steering and biologically calibrated physical landing remain unfinished.
The newer actual-DN-initiated reduced assisted cycle has bounded physical
validation; that does not turn its assumed motor parameters into physiology.

[New visual-path causal controls](visual-causality.md) establish that observed
candidate responses depend on chemical propagation from the currently
stimulated visual populations. They do not establish the flight-state gating
or graded muscle recruitment required for a complete landing.

Primary XML files and SHA256/source receipts are retained under external
`results/flight-steering/primary-evidence-001`. The MANC analysis archive and
verified selected contact-area table are in `manc-analysis-001`; circuit
identity/input results are in `sensorimotor-paths-001`.
