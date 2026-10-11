# Biological fidelity: verified progress and outstanding data

Updated 2026-10-10. This work follows the user's request to move beyond an
artificial-looking behavioral system, not merely its graphics.

## Current causal chain

| Layer | Implemented | Still missing |
| --- | --- | --- |
| Physical environment | Terrain/contact physics, source markers, external finger, saved objects | Calibrated airflow, contact/receptor physics, environment-specific empirical comparisons |
| Visual geometry | Actual eye cameras, sphere angular diameter, field-of-view and occlusion checks; opt-in assumed continuous sphere-rate encoder | Biological spatial/temporal LC4/LPLC2 encoding and receptive-field matching |
| Neural computation | Verified version-630 spiking network and identified GF inputs/readouts | Heterogeneous physiological dynamics and full electrical/VNC connections |
| Electrical transmission | Unit-explicit, charge-conserving current calculation with tests | Measured conductances, capacitances, junction identities/polarity, integration with the correct VNC |
| Muscles | Existing biomechanical actuators; explicit hybrid force assistance; opt-in reduced DNp10-to-leg activation surrogate | Measured neural-to-muscle recruitment and jump/wing deployment mechanics |
| Behavior | Engineered walking/recovery and learned flight benchmarks | Fully neural, robust walking/takeoff/landing/recovery validated against animal behavior |

No incomplete layer is considered solved by the presence of a module.

## Optical correction now wired into the main finger habitat

[fly_looming.py](../scripts/fly_looming.py) uses a **spherical silhouette**
`theta = 2 asin(radius / distance)` instead of the disk approximation
`2 atan(radius / distance)`. Inside/on the sphere it saturates at pi radians.
Expansion velocity uses the consecutive observed angular sizes.

Each eye uses its own distance and history, rather than thorax distance or
a derivative that can jump when the representative eye changes. The combined
input is still a binary broadcast to both visual populations, not a verified
retinotopic per-neuron encoder.

That binary comparison remains the default. The later approved unified-app
[continuous spherical-vision option](graded-visual-feedback.md) assigns separate
assumed LC4/LPLC2 rates, including saved spheres, and measures the full reduced
DNp10 actuator chain with sensory feedback/replay controls. It is not a fitted
response model or verified retinotopy.

The main finger habitat checks both actual eye-camera directions and
configured field of view, then raycasts for intervening scene objects.
An invisible or occluded stimulus cannot activate its visual-population
input. Reappearance starts a fresh angular history rather than producing
an invented derivative spike.

Tests used a compiled FlyGym eye camera and real scene geometry:
placing the finger along the optical axis made it visible; placing an
intervening physical box blocked that eye's visibility.
The geometric helper's tests also exclude stimuli behind the camera.

This is still a simplified center-ray, circular field-of-view approximation:
partial occlusion, full compound-eye projection, receptor temporal responses,
and spatial population encoding are not solved. Aggregate input still gates
100 Hz stimulation through an uncalibrated threshold.

The independent hybrid physical takeoff demonstration retains its original
engineering looming gate to preserve that benchmark; it does not yet use
the calibrated biological encoder (none has been established).
The main low-level finger run now requires eye rendering rather than
silently assuming visual visibility when no eye cameras exist.

## Electrical-synapse current kernel

[electrical_synapses.py](../scripts/electrical_synapses.py) computes each
explicit gap-junction contribution:

```text
I_first[nA] = conductance[uS] * (V_second[mV] - V_first[mV])
I_second = -I_first
```

Tests establish unit correctness, zero current at equal voltages,
antisymmetric contributions/charge conservation, and rejection of
duplicate opposite-direction entries or missing potentials.

**This kernel is not connected to the live brain.** It has no default fly
conductance values, no assumed GF/VNC IDs, no capacitance guesses, and no
claim that all junctions are linear/symmetric. Rectifying electrical
synapses need their measured current-voltage relationship.
It does not convert a chemical-contact count into an electrical conductance.
Integrating it requires explicit neuron identity, measured/model-supported
conductance, membrane capacitance/dynamics and numerical stability checks.

## Quantitative looming calibration is blocked on source data

The public primary abstract establishes that the GF response combines a
linear angular-velocity component and Gaussian angular-size component:
[Ache et al., 2019](https://doi.org/10.1016/j.cub.2019.01.079).

Europe PMC marks the paper as non-open-access and provides no full-text
record. Both publisher full-text and supplemental requests returned HTTP
403 during this review. A public abstract is not enough to establish fitted
coefficients, measurement units/baselines, filtering/latency, or uncertainty.
No unrestricted response-table/code source was verified.

We therefore have **not fitted biological LC4/LPLC2/GF responses**.
Do not claim parameters were extracted or calibrated, use arbitrary rates
as published physiology, or infer missing coefficients from a plotted
description. Authorized article supplements or verified public response
tables are needed; preserve license/provenance and training/test split.

This does not block a clearly labeled model-assumption experiment. The new
graded encoder deliberately uses bounded saturating functions rather than
claiming to reproduce the abstract's linear/Gaussian response components.
Its causal software/physical validation remains separate from biological
curve fitting and empirical equivalence.

## Next evidence gates, by component

1. Obtain accessible quantitative visual-response data; extract exact units,
   response type, latencies and fit protocol.
2. Match input populations/receptive fields and compare predicted GF timing
   and silencing effects, not only spike presence.
3. Identify electrical/VNC paths and gather supported conductance/current-
   voltage and membrane parameters. Integrate into a separately validated
   circuit model before changing the baseline.
4. Map motor neurons to jump/wing effectors and validate recruitment,
   activation/force timing, body trajectories and takeoff variants.
5. Replace hybrid assistance only after those physical/causal tests pass.
6. Validate sustained flight and transitions without hidden reference,
   steering, force or pose-reset substitutes.

The verified hybrid demonstration remains useful as a functional comparison,
but it is not evidence that these biological gates passed.
