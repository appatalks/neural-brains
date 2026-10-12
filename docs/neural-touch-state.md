# Neural touch and internal-state pathways: evidence before assistance

**Reviewed:** 2026-10-11. **Scope chosen by user:** research neural touch and
internal state first, without engineered behavior changes, live stimulation,
automatic resets or recovery/takeoff shortcuts.

## Live observation, not a controlled biological result

In the ongoing interactive episode, the body became inverted: recent upright
cosine was approximately-0.86, while the app still reported "walking".
Physical and neural clocks continued; the observed interval contained zero
network/GF/DNp10 spikes. No mortality, metabolism or biological death model
is implemented, so this is a fallen/stalled controller state, not demonstrated
death of a modeled animal.

The first low-posture point in episode0 was2.17s at approximately
41.63mm/2.23mm, near the original edited objects. Episode1 tilted below0.7
at total21.14s, after object placement events at20.79/20.92s; push events
followed later. This is user-interactive evidence, not pristine reproduction.
Current logs count floor and loose-prop contacts but do not identify every
editor-object contact, so object causation is not conclusively reconstructed.

At inspection, the saved fixed-object list was **empty** after user removal.
It was not restored, and no control, input, reset or restart was performed
during this research.

The main ground reference currently handles arena boundaries, not edited
obstacle geometry. Physics collisions exist, but contact events are not
encoded into the brain. A trained gait observation is not a reconstructed
touch circuit. Rendered eyes also do not imply general scene perception:
normal ground visual input is primarily the configured finger encoder,
with the approximate surface encoder active during flight.

## Primary causal touch target

[Sen et al., Current Biology2019](https://doi.org/10.1016/j.cub.2019.11.004)
(S61; verified indexed abstract) identifies:

```text
anterior body touch / NOMPC-associated mechanosensation
 -> TwoLumps ascending neurons (TLA)
 -> partly via excitatory recruitment of adult MDNs
 -> transient backward walking / retreat from a barrier
```

TLA silencing reduces backward retreat when flies encounter a barrier in the
dark. TLA activation induces backward walking. These support a tactile
escape-from-obstruction hypothesis, **not complete obstacle planning,
self-righting or flight initiation**.
The publisher fulltext returned403 and official lab page503; full methods,
driver details and supplementary correspondence remain uninspected.
No paywall/access restriction was bypassed.

[Bidaye et al., Science2014](https://doi.org/10.1126/science.1249964)
(S62; primary abstract) establishes adult MDN necessity/sufficiency for
barrier-related reverse walking, and MAN involvement in persistent reverse
walking. Adult Moonwalker evidence must not be silently substituted with
larval Mooncrawler circuitry.

## Read-only version-matched audit

[audit_touch_state_paths.py](../scripts/audit_touch_state_paths.py) reuses
already acquired, checksum-verified historical annotations, original brain
inputs, primary identity tables and chemical connection index.
No new asset, neural stimulation, motor decoder or app behavior was added.

### Four MDN outputs confirmed

| Primary MDN group | Canonical side | FlyWire630 root ID | Incoming neurons | Incoming contacts | Ascending partners / contacts |
| --- | --- | --- | ---: | ---: | ---: |
| MDN1/2 | left | `720575940616026939` | 437 | 2,616 | 48 / 271 |
| MDN1/2 | right | `720575940610236514` | 471 | 2,979 | 58 / 371 |
| MDN3/4 | left | `720575940631082808` | 467 | 2,654 | 48 / 300 |
| MDN3/4 | right | `720575940640331472` | 397 | 2,268 | 40 / 283 |

All four are in the127,400-neuron model. Primary Sapkal2024 Table3 calls
them DNp50; historical annotations call them DNpe078/MDN. These labels are
preserved, not silently collapsed into a different identity.
The old code workbook MDN_a pair agrees with canonical sides, while MDN_b
has both sides reversed. The primary table agrees with historical annotations.

The primary table separately matches female FANC and male MANC MDN bodies;
these namespaces are retained and never exchanged with female brain roots.
No exact foreleg/muscle targets or reverse-gait force law are inferred from
the brain IDs.

Each MDN has observed ascending chemical inputs, but those partners are mostly
unnamed. **No direct incoming partner labeled mechanosensory** was found
for these four targets in this audit. This does not prove touch cannot reach
them: the supported route is ascending/polysynaptic, and labels are incomplete.

No exact `TLA`/`TwoLumps` label occurs in the pinned annotation fields.
Generic ascending cells are therefore not promoted to TLA. An old workbook
alias `iAN-MDN` points to GABA-predicted ascending inputs; it is not a substitute
for the experimentally excitatory TLA pathway.

### Sensory/state inventory, with model membership

| Category | Annotation rows | Present in model | Important limit |
| --- | ---: | ---: | --- |
| Ascending cells | 2,364 | 2,319 | Only21annotation rows have a cell/hemibrain type name; function unresolved |
| Head-bristle mechanosensory cells | 302 | 302 | Head touch is not leg/thorax contact identity |
| Eye-bristle mechanosensory cells | 1,112 | 1,111 | Not a generic whole-body collision sensor |
| Predicted octopamine | 152 | 134 | Includes12non-neuron annotation rows and other classes; not a stimulation population |
| Explicit OA-family type names | 46 | 46 | Anatomy labels alone do not establish state/driver equivalence |

No exact FeCO, NOMPC, Tdc2 or Tbh label was found. Absence of a gene-marker
string from a cell-type table is not evidence that the receptor/enzyme is
biologically absent.
Likewise, the unnamed ascending population is not a validated posture
encoder merely because it projects toward the brain.

Original processed signed-contact weights and historical transmitter
predictions are distinct upstream proxies. Both are retained; signs are not
recomputed from the newer annotation or called measured conductances.

External evidence: `results/touch-state/identity-path-audit-001/audit.json`.

## Proprioception and behavioral-state feedback are distinct

[Chen et al., Current Biology2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8665017/)
(S63; selected primary results) distinguishes:

- FeCO claw position signals.
- Hook movement/direction signals.
- Club movement/vibration signals, including downstream9Ba/10Ba processing.
- 9Ba chemical acetylcholine input and10Ba evidence for mixed local
  chemical/electrical transmission.

Some10Ba projections reach the brain, and vibration-related walking pauses
are relevant. These are not a calibrated force-on-any-geom detector. The
reviewed VNC proprioceptive circuits, peripheral sensory cells, gap-junction
parameters and body receptor locations are not reconstructed in the current
brain-only model or148-cell motor subset.

[Chen et al., Nature Neuroscience2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10076225/)
(S64; selected primary results/methods) shows ascending populations encoding
self-motion and discrete behavioral states, preferentially targeting AVLP
and GNG. Most recorded activity was not explained by an individual joint
angle alone. These calcium/state results do not supply exact10ms
spike-to-posture gains or connectome-root equivalences.

## Internal drive is not a takeoff timer

[Yang et al., PNAS2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4413307/)
(S65; selected adult results) establishes octopamine involvement in delayed
starvation-induced locomotor hyperactivity. Virgin-female assays use
hours/days, nutrient deprivation and broad genetic populations.
Nutrient supply and food cues can suppress that activity; feeding-state
effects and locomotor-state effects are separable.

This does not justify turning elapsed simulation seconds into random flight
or stimulating every octopamine-predicted cell. The model has no calibrated
energy assimilation, hunger hormones, neuromodulator release/receptors or
metabolic mortality. Normal LIF resting activity is zero, and the inputs
currently supply only specified sensory/intervention drive.

The most clearly named local OA candidate found is **OA-VPM4**:

| Canonical side | Historical FlyWire630 root | Incoming neurons / contacts |
| --- | --- | ---: |
| left | `720575940624971243` | 1,002 / 3,110 |
| right | `720575940627702665` | 617 / 1,693 |

[Youn et al., PLoSOne2018](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0198362)
(S66; selected primary abstract/introduction) supports sucrose-related
proboscis extension and octopamine/OAMB modulation of sugar sensory responses.
**That is feeding evidence**, not an identified general arousal, spontaneous
walking or takeoff controller. Driver-to-root correspondence and quantitative
modulation remain to be validated.

Homogeneous fast signed chemical weights cannot silently stand in for slow
octopamine receptor-dependent gain/state changes.

## Bounded next neural work

1. Resolve adult TLA and relevant NOMPC sensory driver/morphology correspondence
   in a pinned brain/VNC dataset. Do not pick unnamed ANs or a near-name alias.
2. Specify anterior-touch input geometry/force/timing from accessible primary
   methods, with no-touch, posterior/off-target and matched input controls.
3. Test actual TLA-to-MDN recruitment in a **neural-only** experiment, including
   sensory/source disconnection and MDN silencing; do not change live gait.
4. Separately audit VNC reversal/proprioceptive/muscle paths and physical
   decoding. Negative reference speed in a learned policy is not reconstructed
   reverse-walking physiology.
5. For internal drive, distinguish nutrient state, sensory gain and motor
   initiation; first choose a validated adult target and measurable state
   response. Feeding OA-VPM4, starvation locomotion and takeoff are not
   interchangeable evidence.

Source/method/identity and transmission gaps are explicit. No forced
self-righting, contact-triggered scripted turn, takeoff timer or injected live
neural arousal was introduced.

Reproduce the read-only audit with existing assets:

```bash
.venv/bin/python scripts/audit_touch_state_paths.py \
  --data-dir "${FLY_DATA_DIR:?Set verified external storage}" \
  --output-dir "$FLY_DATA_DIR/results/touch-state/audit-$(date +%Y%m%d-%H%M%S)"
```

Validation:288offline tests run, eight skipped, no failures;17focused
identity/namespace tests also pass. The actual read-only audit completed with
verified assets. Neither offline tests nor connectivity inspection validate
touch encoding, internal-drive physiology or animal behavior.
