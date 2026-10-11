# Flight steering: evidence before decoding

The user explicitly chose neural steering research rather than another
engineered obstacle-avoidance/turning controller. The existing learned
straight-reference flight remains labeled as a motor comparison. No random
turns, wall repulsion or invented DN-to-wing gain is added.

## Primary evidence checked

[Namiki et al., 2021 preprint](https://www.biorxiv.org/content/10.1101/2021.08.05.455281v1)
describes a population of DNg02 descending neurons projecting from visual
output regions to dorsal flight neuropil. Population activation changes
wingbeat amplitude over a wide range; functional imaging shows responses
to visual motion. This establishes a candidate flight-control population,
not a complete navigation or turn decoder.

[Palmer, Omoto and Dickinson, 2022 submitted preprint](https://authors.library.caltech.edu/records/drvbj-nkj15)
tests the optomotor response. Silencing DNg02 reduces the optomotor response
and coordinated head/abdomen/hind-leg changes. However, **unilateral
optogenetic activation produces bilaterally symmetric wing-amplitude
increases**, not the asymmetric wing changes of natural optomotor steering.
The authors argue that other descending classes targeting steering-muscle
motor neurons are also needed.

The Namiki population study is now verified as a final
[Current Biology 2022 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9206711/)
(DOI 10.1016/j.cub.2022.01.008), not only the 2021 preprint.
The Caltech optomotor source above remains explicitly submitted/preprint.
Neither establishes a calibrated neural-to-muscle flight decoder.

[Primary MANC wing-circuit results](https://pmc.ncbi.nlm.nih.gov/articles/PMC13384506/)
identify DNa04/DNa05 as steering candidates and trace paths through wing
contralateral haltere interneurons (w-cHINs). They emphasize phase-locked
haltere/steering-muscle interactions and note that electrical synapses are
not resolved by their EM method. Membrane contact area suggests possible
electrical connections; it is **not a conductance measurement**.

The acquired CC-BY-4.0
[analysis archive](https://zenodo.org/records/20532930) contains a putative-
electrical table with five w-cHIN groups. Its supplied MD5 was verified;
source/member checksums and provenance are retained externally. There are
no measured conductance values in that table.

## Version-matched identity audit

[audit_flight_steering.py](../scripts/audit_flight_steering.py) verifies the
existing historical annotation and processed brain inputs, then selects
only explicit `DNg02` or `DNg02_<subtype>` cell-type labels.
Near-name labels such as DNg20/DNg26 are not included.

The audit found **27 candidates, all present in the 127,400-neuron model**:

| Historical subtype | Count |
| --- | ---: |
| DNg02_a | 9 |
| DNg02_b | 8 |
| DNg02_c | 2 |
| DNg02_d | 2 |
| DNg02_e | 2 |
| DNg02_f | 2 |
| DNg02_g | 2 |

These annotations are not proof that each subtype is functionally equivalent
to every cell targeted by a genetic driver in the papers. IDs remain strings,
left/right annotations are retained, and unmatched model IDs would be reported.
An initial exact-unsuffixed-label-only audit found zero cells; that result
is retained separately rather than overwritten. Inspection revealed explicit
subtype names, which the corrected selection preserves.

External evidence: `results/flight-steering/subtype-audit-001/dng02.json`.
No neurons were stimulated and no motor decoder was wired by this audit.

## Required next causal tests

1. Verify driver-to-connectome correspondence for DNg02 subtypes and identify
   the additional steering pathways/motor-neuron targets.
2. Trace version-matched visual motion inputs; fit an encoder only with
   quantitative response data, not aggregate retinal brightness.
3. Gather VNC identities, muscle recruitment/activation timing and wing
   kinematic transfer relationships. Brain-only chemical edges cannot supply
   these missing mechanisms.
4. Compare predicted optomotor timing/wing asymmetry with held-out stimuli
   and silencing/sham controls.
5. Preserve the existing bilateral-amplitude result as a constraint: do not
   map left/right DNg02 counts directly to opposite turns without evidence.

Steering/optomotor stabilization is also not identical to obstacle avoidance,
goal-directed navigation, or landing. Each needs its own causal evidence.

## Steering identity ambiguity and landing paths

[The new sensorimotor audit](../scripts/audit_sensorimotor_paths.py) checks
both historical annotation fields. It finds two different pairs associated
with each of DNa04 and DNa05:

- DNa04 cell-type labels (hemibrain PS015) versus DNae004 cell-type labels
  carrying the historical hemibrain name DNa04.
- DNa05 cell-type labels (hemibrain PS028) versus DNae006 cell-type labels
  carrying the historical hemibrain name DNa05.

All candidates remain separate and are flagged as ambiguous type correspondence.
Selecting either pair by name alone would silently choose a different circuit.
Resolving their relationship to the primary experimental/male-cord types is
a prerequisite to intervention claims.

The same audit finds bilateral DNp07 and DNp10 through explicit historical
hemibrain annotations, and retains every incoming chemical-contact total and
the strongest annotated upstream groups. All 12 steering/landing candidates
are present in the model. DNp07's strongest annotated upstream group is LPLC4
(810 left / 638 right contacts); this is measured dataset connectivity,
not an experimentally calibrated looming encoder. No LPLC3 input assignment
was established from the reviewed landing paper.

External evidence: `results/flight-steering/sensorimotor-paths-001/audit.json`.
The audit does not modify the active motor controller or add neural stimulation.

## Live candidate observations

With the takeoff circuit and sparse telemetry enabled, the worker now returns
exact interval counts for **39 version-matched candidates**: the 12 separately
retained steering/landing identities and 27 DNg02-subtype cells. Counts come
from the existing full-network monitor, not a separately driven circuit.
The client checks each readout against the corresponding sparse neuron count.

The browser's **Steering and landing circuit readouts** panel shows these
counts, allows selection and chemical-connection inspection, and labels
ambiguous steering identities. Its displayed counts follow the selected
live/historical firing view. It does not turn these counts into motor commands.

An explicit one-second LC4/LPLC2 Poisson probe produced 58,750 network spikes
and activity in seven observed candidates:

| Annotation | Side | Spikes |
| --- | --- | ---: |
| DNae004 / historical DNa04 | Right | 2 |
| DNae004 / historical DNa04 | Left | 1 |
| DNae006 / historical DNa05 | Left | 2 |
| DNa05 / hemibrain PS028 | Left | 15 |
| DNa05 / hemibrain PS028 | Right | 7 |
| DNp07 | Right | 27 |
| DNp10 | Left | 15 |

This artificial input is not a calibrated visual/landing experiment.
Candidate spiking does not establish natural steering, flight-state gating,
or muscle recruitment. The network/legacy output fields matched the
readout-disabled run exactly; reset replay matched and the no-input control
was silent. External evidence:
`results/flight-steering/candidate-readout-parity-001`.
The repeatable real-network regression is in
[test_fly_activity.py](../tests/test_fly_activity.py).

## Primary matching-table acquisition status

The primary MANC supplementary table is identified as **DN typing, tracts and
light-level matching**. The published download URL returned an HTML preparation
interstitial rather than CSV. A second request through the official Europe PMC
supplementary-files API timed out. Both failed receipts are retained externally
as `manc-matching-001` and `manc-matching-002`; neither is treated as acquired
matching data.

The table was subsequently acquired from the
[publisher's version-2 CSV](https://cdn.elifesciences.org/articles/96084/elife-96084-supp1-v2.csv).
It has 1,328 rows and 152,740 bytes. Author names use Windows-1252 rather than
UTF-8; the raw payload is preserved and its SHA256 is pinned in the audit.

| Published MANC type | Systematic type | Group | Body IDs | Matching confidence (1–5) |
| --- | --- | --- | --- | ---: |
| DNa04 | DNut001 | 11123 | Left 11216; right 11123 | 3 |
| DNa05 | DNut002 | 12275 | Left 12275; right 12319 | 3 |
| DNp07 | DNxn027 | 11150 | Left 11228; right 11150 | 5 |
| DNp10 | DNxl018 | 10732 | Left 10835; right 10732 | 5 |

These are published matching scores, **not probabilities or physiological
validation scores**. The primary table establishes the male VNC type/body
assignments. It does not resolve which conflicting historical female FlyWire
pair matches each experimental steering type. The audit keeps MANC body IDs
in a separate namespace and explicitly marks FlyWire correspondence as
name-level only.

Evidence: `results/flight-steering/manc-matching-004` and
`matched-sensorimotor-paths-001`.

## Causal model controls now implemented

[Visual chemical-output disconnection tests](visual-causality.md) now compare
intact, sham, LC4, LPLC2, both-disconnected and no-input networks at two seeds.
Both-disconnected sources continue firing while GF and all observed candidate
readouts become silent; sham and reset checks pass exactly.
This is causal model evidence, not calibrated animal steering or landing.
