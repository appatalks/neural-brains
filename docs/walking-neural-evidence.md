# Walking initiation and stopping: pathway audit

The subsequent [touch/internal-state research](neural-touch-state.md) identifies
adult TLA-to-MDN reversal as a relevant obstacle-contact hypothesis, confirms
four MDN outputs in the current model, and preserves unresolved TLA sensory
identities. User chose research only: no live touch/arousal/recovery input or
engineered behavior was added.

**Reviewed:** 2026-10-11. **Status:** primary identities resolved, bounded
neural-path causal tests completed, optional exact readouts implemented.
Not a neural gait implementation or biological reproduction.
The user selected this milestone before adding another engineered navigation aid.

**Next milestone completed:** [BDN2 VNC circuit evaluation](bdn2-vnc-reproduction.md)
found genuine rate-model core rhythms with causal disconnection controls in
three author-archived parameter sets. The subsequent loader correction uses
actual HDF5 weight masks rather than output-activity masks, and a separately
approved native CPU solver is implemented. Strict rate conformance still fails;
full4,604-cell parent diagnostics also fail the stronger averaged antagonist
gate. This is a putative rhythm core, not a validated muscle/gait interface.

The subsequent [independent reference and assumed joint
interface](independent-vnc-joint.md) passes33numerical checks per reference
and24physical checks in the final bench run, including fresh seed429.
This is an externally tethered single-joint rate proxy, not current brain-spike
control or calibrated gait. Normal walking defaults are unchanged.

The next [genuine brain-spike-to-joint test](brain-spike-joint-test.md) passes
24brain-packet controls, but the assumed transfer fails4of66coupled checks.
One held-out brain seed430 produces the declared joint response; two
development seeds do not. No gain was fitted to rescue the failures.

The later [matched-input relay uncertainty study](relay-uncertainty-test.md)
predeclares nine hypotheses and selects only from development420/421.
Both matched brain-control cohorts pass22checks; the selected20ms/250mean
relay passes25/26held-out physical checks and remains failed on seed432.
This is not deployed or claimed physiologically calibrated.

## Latest resolution and actual causal tests

### Primary identities supersede the old code workbook's side labels

Acquired the publisher's primary Supplementary Table 3 (S56), 25,598 bytes,
provider-MD5 verified as `1b2a859f5099ff752171d3291f171e8d`; local SHA256
`41c0f799193faf13477a7b537fa3d37d72d88c8cc048ad56f229536169c04d04`.
Parent primary article CC-BY-4.0 was verified in its full-text XML.
Only this selected asset was acquired with a 100,000-byte cap; receipts and
the workbook remain outside Git.

The primary table explicitly confirms BDN2 = the old BPN_SEZ_DN2 pair,
oDN1 = P9-oDN1, and all six BRK brain projections. Its canonical sides agree
with the historical annotations. The old code workbook reversal remains
recorded; it is not a reason to swap root IDs or silently rewrite that asset.

- BDN2 left `720575940612364530`, right `720575940647228468`.
- FG left `720575940628755815`, right `720575940611160930`.
- oDN1 left `720575940626730883`, right `720575940620300308`.
- BRK brain pairs: `720575940630424407` / `720575940630012663`,
  `720575940623700661` / `720575940620600929`, and
  `720575940620631974` / `720575940635632888` (left / right).

The primary table separately matches BDN2 to MANC DNxl058 bodies
10093/10339 and oDN1 to DNxl054 bodies 10656/11070. Female FANC IDs and
male MANC IDs remain separate namespaces; they are not grafted into the
female brain's connectivity.

BPN tests select the 12 Type1/CL210 cells. Other BPN classes remain excluded.
One primary row says Type1 but has SMP461 rather than CL210 and corresponds
to an old Type4 workbook entry; this conflicting row is excluded explicitly,
not silently reassigned. The resolved audit is external
`results/walking-paths/identity-audit-002/audit.json`; 001 remains historical.

### Walking/halting coactivation: 176 trials, 152/152 checks passed

[test_walking_causality.py](../scripts/test_walking_causality.py) ran 22 cases
at seeds 420/421/422/425 at both 0.05 ms (paper method timestep) and 0.1 ms
(actual live worker timestep): 88 trials and 76 checks per timestep.
Seed 425 was reserved prospectively for this walking experiment.
Each trial runs 1 s, measured in two 500 ms halves, with 150 Hz evoked input.
Protocols, source hashes, input receipts and exact sparse count arrays were
saved before/through execution.

Verified outcomes include genuine descending recruitment, exact identity-sham
and reset parity, silent no-input controls, source-only firing after recurrent
output disconnection, target-clamp silencing including direct input, and exact
pre-intervention parity before delayed FG activation.

At 0.1 ms, BPN-driven BDN2 counts at the four seeds were
160/170/167/173; with FG coactivation, all four were zero; with BB
coactivation, counts were 129/145/142/144. At 0.05 ms, FG left one BDN2 spike
at seed 422. P9 recruited oDN1; BB strongly suppressed that output.
BRK reduced BPN output but did not eliminate it, which is consistent with
the missing VNC-specific mechanical brake rather than a universal brain OFF
switch.

Evidence: external `results/walking-paths/causality-001` and `causality-002`.
This tests the preserved original model, not spike-for-spike reproduction
of the paper's modified code/data or its 30-trial averaged response surfaces.

### Existing sugar input -> FG -> walking output: retained partial failure

The primary paper's Fig. 5 supports investigating sugar GRNs recruiting FG
and suppressing walking-promotion outputs. A separately frozen sugar protocol
used the existing 21 sugar input IDs at 100 Hz and walking input at 150 Hz,
0.1 ms timestep, seeds 420/421/422/426; seed 426 was prospective for this
new experiment. Sixty trials completed: **42/44 checks passed; overall FAILED**.
No thresholds or gains were changed to turn that into a pass.

| Seed | BPN -> BDN2 | BPN + sugar -> BDN2 | Same with FG outputs disconnected | Same with FG voltage clamped |
| --- | ---: | ---: | ---: | ---: |
| 420 | 160 | 39 | 125 | 125 |
| 421 | 170 | 38 | 122 | 122 |
| 422 | 167 | 37 | 123 | 123 |
| 426 | 174 | 45 | 120 | 120 |

The BPN/BDN2-specific checks passed at every tested seed. Sugar source
disconnection left only directly injected sensory spikes and no MN9/FG
recruitment. FG output disconnection preserved FG spikes; FG voltage clamp
removed them. Both released BDN2 inhibition, while identity shams matched
exactly.

The negative result is important: at seed 421, P9+sugar oDN1 counts were 17,
and remained 17 with either FG output disconnection or FG voltage clamp.
Those two predeclared release-of-inhibition checks failed. Consequently,
**BPN/BDN2 is the more robust path among these tested protocols**, not a
proven globally optimal controller. P9 and its negative results are retained.

Evidence: external `results/walking-paths/sugar-causality-001`.
This runner has a different Poisson-object/chunk schedule from the live worker;
it is not asserted to be the exact sugar baseline spike stream. Separate
readout on/off tests below establish live-worker baseline preservation.

### Implemented: optional observation, not an invented motor decoder

`--walking-readouts` on the unified launcher adds **28** primary-verified
P9/BPN/FG/BB/BDN2/oDN1/BRK cells to the existing 39 readouts, totaling 67.
The worker reuses its existing count monitor, the client checks every count
against sparse activity, and the browser supports current/historical inspection
and real chemical connections with an observation-only heading.
There is no new neural input, recurrent connection, spike threshold, gait
command or metabolic model. The flag defaults off.

Actual worker on/off tests preserved the complete visual and feeding
responses exactly, including 58,750 visual network spikes and the feeding
baseline's 65 MN9 / 9,840 network spikes; reset replay and no-input silence
passed. Visual input produced three BDN2 spikes, while sugar alone recruited
64 FG and seven BB spikes at seed 420. This is also a warning against mapping
any isolated BDN2 spike to automatic walking without a calibrated state/motor
interface.

Evidence: external `results/walking-paths/readout-parity-002`. Earlier 001
failed a mistaken test expectation of 30 new cells/69 total; its files and
failure summary are retained. The implementation correctly exports 28/67.
A single 0.2 s bounded app test at port 8840 completed with this flag and
released the port; no persistent app was started or user session reset.

Latest full offline suite: **257 tests run, six skipped, no failures** in the
existing isolated flight environment with EGL. The real-network readout test
was also run explicitly and passed.

### Remaining implementation gate

Identity and brain-side causal dependence are now supported. Calibrated
VNC transmission, proprioceptive feedback, muscle activation/force and
state-dependent spontaneous initiation are still missing. The primary paper
itself states that intrinsic firing in this model is zero and Poisson input
is its only external drive.

Do not use a one-spike gate or a guessed BDN2-rate-to-speed gain and label
it reconstructed neural walking. A reduced neural-request/learned-gait
surrogate would be a separate explicitly disclosed design, not a physiological
solution implied by these results. The next scientific target is the
BDN2 VNC/muscle interface with measured kinematic and causal acceptance tests.

## Historical initial audit (before primary resolution)

The initial alias and side blockers below describe the preserved 001 audit;
the newer primary resolution above supersedes them.

## Biological question

Can identified walking-promotion pathways recruit descending output through
the preserved brain network, and can identified halting neurons suppress that
output in the context-dependent way reported experimentally?

This is narrower than autonomous walking, obstacle negotiation or calibrated
muscle control. A neural walking request passed to a learned gait would be
**brain-linked initiation with a learned motor surrogate**, not reconstructed
neural gait. The present live app remains learned, always-requested walking.

## Primary evidence reviewed

| Pathway | Supported result | Important boundary |
| --- | --- | --- |
| P9 | Activation initiates forward walking with ipsilateral turning; visual/courtship inputs are reported | Courtship necessity experiments concern males pursuing females; not a generic female navigation decoder |
| BPN | Higher-brain neurons initiate fast straight walks; unilateral activation does not impose a turn bias | BPN is not itself a descending neuron; calcium correlates with a subset of spontaneous bouts, not every walk |
| oDN1 | Activation initiates forward walking, including in decapitated flies | Reported silencing did not reduce forward velocity in the tested assay |
| BDN2 | Activation initiates walking; silencing reduces forward velocity; calcium correlates with forward, not angular, velocity | These results do not provide a calibrated spike-to-speed or muscle-force law |
| Foxglove (FG) | GABAergic walk-OFF pathway suppresses forward components; partly suppresses BPN-driven walking | Not universal suppression of all locomotor commands |
| Bluebell (BB) | GABAergic walk-OFF pathway strongly suppresses P9-driven forward turning | Do not collapse it into the same decoder as FG |
| Brake (BRK) | Six ascending VNC neurons arrest stepping and increase leg-joint resistance, also influencing brain pathways | Brain-side projections alone cannot implement physical braking |

Sources: Bidaye et al., [Neuron 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC9435592/)
(DOI 10.1016/j.neuron.2020.07.032; S53) and Sapkal et al.,
[Nature 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446846/)
(DOI 10.1038/s41586-024-07854-7; S54).
Selected primary results and stopping/feeding/kinematics methods were reviewed;
the papers' experimental data were not reproduced or fitted.

## Reproducible local audit

[audit_walking_paths.py](../scripts/audit_walking_paths.py) uses the approved
paper-linked `flywire_ids_630.xlsx` from release v1.0.0, commit
`ae2a5e2eace007fc7f186278538047b48017a087` (S55). The selected asset is
63,463 bytes with verified Git blob
`48b3e0a5d29ede0b888aecc1b7134544e2ed3dd9` and acquired SHA256
`8ced5aef414d8dd5394f3edb1a8c5bdaf5a9b04789e110c7f87e7ef95afa0186`.
Only this workbook was acquired, with a 100,000-byte limit through
[datasets.py](../scripts/datasets.py). Raw workbook and receipt stay outside Git.

Current upstream metadata reports MIT, but the pinned release has no LICENSE.
Workbook-specific terms remain unresolved; the user explicitly approved local
audit acquisition, not redistribution. No copy of the workbook is committed.

The audit reads root IDs as strings without float coercion, joins the verified
historical v1.1.0 female FlyWire630 annotations and original 127,400-neuron
model, and reuses the checksum-bound sparse chemical connection index.
It selects FG, BB, P9, P9-oDN1, BPN_SEZ_DN2, DNa02 and the six workbook
BPN_1a-f pairs. Other similarly named BPN/STOP/MAN entries are not substituted.

**Result:** 24 candidates, 24 present in the preserved model, no missing IDs.
All 24 have opposing workbook-versus-annotation side labels. Both labels remain
in the report; no orientation convention or corrected laterality is assumed.
This blocks side-specific intervention/steering interpretation, not inspection
of the exact root IDs.

| Workbook name | Workbook ID_left | Workbook ID_right | Local annotation type |
| --- | --- | --- | --- |
| FG | `720575940611160930` | `720575940628755815` | CB0890 |
| BB | `720575940635166571` | `720575940631168057` | DNge195 |
| P9 | `720575940627652358` | `720575940635872101` | historical DNp09 |
| P9-oDN1 | `720575940620300308` | `720575940626730883` | DNge159 |
| BPN_SEZ_DN2 | `720575940647228468` | `720575940612364530` | DNge162 |

Each ID in the table has the **opposite** historical annotation side.
The DNp09 annotation search also finds a separate DNpe060 pair; the audit
retains the paper workbook's P9 IDs rather than replacing them by name.

The workbook calls BPN_SEZ_DN2 "FOMO" and a major FG output, but does not
explicitly call it BDN2. Its correspondence to the paper's BDN2 remains
**provisional** pending primary Supplementary Table 3/driver confirmation.
No BRK IDs are assigned from the workbook's similarly named STOP/MAN rows.

### Observed chemical-path constraints

Summing contacts from both FG cells and both BB cells separately:

| Exact target ID | Workbook target name | FG contacts | BB contacts |
| --- | --- | ---: | ---: |
| `720575940620300308` | P9-oDN1 | 66 | 91 |
| `720575940626730883` | P9-oDN1 | 48 | 92 |
| `720575940647228468` | BPN_SEZ_DN2, provisional BDN2 alias | 446 | 5 |
| `720575940612364530` | BPN_SEZ_DN2, provisional BDN2 alias | 581 | 13 |

The original model assigns negative signed-contact proxies to these FG/BB
edges, consistent with their predicted GABA labels. Contact counts and signs
are not conductances, membrane parameters, firing-rate predictions or actuator
gains. Connectivity differences support a testable hypothesis; they do not
prove the simulated suppression before an actual intervention experiment.

Evidence bundle: external `results/walking-paths/identity-audit-001/audit.json`.
It contains exact incoming totals, selected-path edges, top input types,
annotation labels, model membership and all side discrepancies.

```bash
.venv/bin/python scripts/audit_walking_paths.py \
  --data-dir "${FLY_DATA_DIR:?Set the verified external data directory}" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/identity-audit-$(date +%Y%m%d-%H%M%S)"
```

This reads already acquired inputs; it does not stimulate neurons, alter
motor controllers, start a browser app or download another asset.

## Next acceptance gates, not claimed results

1. **Resolve identities:** confirm BDN2 and BRK using primary Supplementary
   Table 3, and investigate the systematic side reversal. Do not substitute
   male MANC body IDs for female FlyWire roots.
2. **Freeze a neural-only protocol before running it:** record stimulus
   populations/rates/durations, model hashes, simultaneous versus delayed
   interventions and seeds. Compare no-input, walk-only, halt-only, sham,
   walk-plus-halt and output-silenced trials. Use development seeds 420-422
   and reserve seed 425 for this experiment's prospective test; no result
   is asserted here. Injection must be labeled evoked, not spontaneous.
3. **Test the exact output:** compare genuine contiguous spike counts at
   identified descending targets. Pre-register rate/suppression criteria
   against the published protocol or experimental data before fitting; do
   not choose a convenient motor threshold after observing outcomes.
   Verify no-input silence, exact sham/reset replay and effective silencing
   even when stimulated cells receive direct input.
4. **Account for model differences:** the published walking-model Parquet
   is 86,631,045 bytes versus 86,630,944 in our original model. Its code
   supports a different intervention protocol. No replacement, equivalence
   or published spike-parity reproduction is claimed.
5. **Only then test embodiment:** obtain justified VNC/muscle and
   proprioceptive mechanisms, or explicitly approve a reduced learned
   motor surrogate. Require neural causal dependence of walking requests,
   stable real ground contact, advancing brain/body clocks during stops,
   no pose reset and successful restart after stimulus withdrawal.
   The paper's sucrose assay defines stops as smoothed speed <2 mm/s for
   ten video frames; preserve its acquisition cadence and context when
   using that metric rather than calling a safety pause biological halting.

Neither spontaneous initiation, calibrated sensory drive, neural energy
metabolism, neural leg coordination nor obstacle-responsive neural walking has
been implemented by this audit.

## Validation

Actual local audit completed with checksum-verified assets and the existing
connection index. Full offline suite in the pinned flight environment with EGL:
247 tests run, 5 skipped, no failures at that initial audit milestone. The system `python3` run encountered
13 existing MuJoCo-dependent test errors because MuJoCo is not installed there;
no dependencies were installed or environments mixed. These tests validate
tooling, not biological behavior.
