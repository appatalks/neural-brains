# Neural takeoff: first evidence review

An explicitly approved [experimental hybrid physical takeoff](hybrid-physical-takeoff.md)
now demonstrates GF-triggered motor assistance and continued learned flight.
It does not resolve the biological encoding/electrical/VNC/muscle gaps below.
This document preserves the brain-side evidence and validation boundary.

**Reviewed:** 2026-10-10. The user selected neural takeoff research before
an engineered walk-to-flight transition. No takeoff controller is implemented
or claimed by this review.

## Supported starting hypothesis

The best-supported initial target identified here is **looming-evoked escape
takeoff**, not spontaneous flight or general navigation:

```text
looming angular size/velocity
    -> LPLC2 / LC4 visual populations
    -> giant fiber (GF), alongside parallel escape pathways
    -> thoracic interneuron/motor pathways
    -> jump and flight-muscle responses
```

This diagram summarizes literature relationships, not a ready-to-run,
version-matched simulation graph.

| Evidence | Reviewed support | Does not establish |
| --- | --- | --- |
| [von Reyn et al., 2014](https://doi.org/10.1038/nn.3741) | Primary abstract: relative GF spike timing selects short versus long looming escape sequences; short sacrifices stability for speed | GF activation alone is a complete flight controller |
| [Ache et al., 2019](https://doi.org/10.1016/j.cub.2019.01.079) | Primary abstract: LC4 supplies angular-velocity component, LPLC2 size component; both synapse onto GF; LPLC2 silencing changes looming responses | Raw camera intensity maps directly to GF or motor firing |
| [Namiki et al., 2018](https://doi.org/10.7554/eLife.34272) | Primary abstract: descending pathways connect brain and nerve-cord motor neuropils, with distinct walking/flight organization | All identified DNs cause takeoff, or a complete functional transfer function |
| [GF electrical coupling study, 2018](https://www.eneuro.org/content/5/6/ENEURO.0346-18.2018) | Article abstract/introduction: mixed chemical/electrical GF circuitry; TTMn/TTM jump pathway and PSI-to-DLM motor pathway | A chemical-only graph contains all important transmission mechanisms |

Abstract-level review is not full methods/supplement verification. The 2018
electrical-coupling study also shows the classic GF system includes more
coupled neurons than a simple linear diagram suggests. Do not ignore those
connections or invent missing conductances/delays.

## Why the current habitat cannot naturally take off yet

1. **Only taste inputs are connected to the live brain worker.**
   Retinal-intensity steering is an engineered baseline; it does not encode
   LC4/LPLC2 looming responses or drive verified GF neurons.
2. **Version-630 model inputs are a chemical-connectivity brain model.**
   The live worker does not model the thoracic GF/VNC electrical pathways or
   muscular effectors. Turning on missing wing actions cannot repair that.
3. **Historical version-matched IDs are now established for the brain-side
   candidate populations** (see audit below); their downstream VNC/motor
   identities remain unresolved. The current systematic annotation
   [column documentation](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md)
   explicitly defines root IDs for release **783**, not our version **630**.
   Cell names, similar IDs, and the same species do not prove correspondence.
   The historical v1.1.0 release explicitly supplies 630 root IDs and was
   verified separately rather than remapping those current annotations.
4. **The walking body is legs-only controlled.** The separate flight backend
   uses aerodynamic wing actuation and an already-airborne initialized
   reference-tracking policy. It is not a ground-to-air physiological decoder.
5. **Escape initiation differs from sustained flight.** An observed GF spike
   cannot legitimately become "start trained flight" without an explicitly
   modeled and validated motor handoff.

Do not use MN9 to trigger takeoff, invent GF IDs, delete electrical pathways,
or turn off gravity as a substitute for a neural motor model.

## Required next bounded work

### A. Identify version-matched circuit

- Acquire a pinned annotation release and map LC4, LPLC2, GF and relevant
  parallel escape populations to verified IDs.
- Obtain verified 630 correspondence, or reproduce/migrate the model to 783
  as a separate experiment before using 783 annotations.
- Explore full MaleCNS coverage for the brain-to-VNC pathway; keep specimen,
  sex and correspondence explicit. Do not silently graft male/female maps.
- List observed chemical contacts and missing electrical/motor connections
  with source, uncertainty and data availability.

**Acceptance:** explicit IDs and source versions, checked edges, unmatched
IDs counted, and a documented boundary between measured data and assumptions.

### B. Visual input -> neural escape response

- Implement an environment looming stimulus with controlled angular size,
  velocity, approach direction and time.
- Review primary response curves and intervention experiments before
  choosing receptor/LC4/LPLC2 encoding parameters.
- Validate GF response timing and LPLC2/LC4 manipulation outcomes against
  those measurements, separately from body actuation.

**Acceptance:** actual network response with matched stimulus timing and
causal controls; no rule-based takeoff event hidden in the decoder.

### C. Neural escape response -> takeoff mechanics

- Model or justify electrical/chemical thoracic transmission.
- Map motor neurons to supported jump/wing effectors with timing and force
  parameters, including uncertainty.
- Use one compatible body model through ground contact, leg extension,
  wing deployment and subsequent airborne dynamics.
- Measure force/contact sequence, launch velocity, latency, orientation
  and sustained post-takeoff behavior. Distinguish short/long escape variants.

**Acceptance:** predeclared kinematic and neural intervention tests.
Flying demos or a single transient hop do not satisfy it.

## Current decision

Continue the existing autonomous hybrid habitat and real feeding circuit.
Takeoff remains unavailable until the above evidence and tests exist.
Next progress should be exact circuit identification and looming-to-GF
validation—not an automatic scripted switch to the flight policy.

## Version-630 identity and chemical-edge audit completed

Historical annotation tag **v1.1.0**, commit
`df6bb136f5b3d91c3992df4e8de2642329e2a384`, explicitly defines `root_id`
as FlyWire **630** in its
[column documentation](https://github.com/flyconnectome/flywire_annotations/blob/df6bb136f5b3d91c3992df4e8de2642329e2a384/supplemental_files/Supplemental_files_columns.md).
This resolves the earlier brain-side ID/version obstacle without changing
the independently validated live model.

The 21,714,061-byte annotation TSV was acquired through the existing
downloader and verified against its pinned Git blob hash. Public access
does not establish redistribution rights: asset-specific license terms are
still unverified and explicitly recorded in the catalog.

[audit_takeoff_circuit.py](../scripts/audit_takeoff_circuit.py) validates
source hashes, exact type labels, neuron membership, and both presynaptic/
postsynaptic ID-to-index mappings in the original model.

Found in the annotated/model intersection:

- **104 LC4**, **210 LPLC2**, and **2 giant fibers**.
- **Zero missing candidate model IDs**.
- Right GF/DNp01: `720575940632499757`.
- Left GF/DNp01: `720575940622838154`.
- GF assignment requires both `cell_type = DNp01` and
  `hemibrain_type = Giant Fiber`; LC4 selection explicitly excludes LC40/LC45.

Direct chemical inputs in the existing model export:

| Population | GF target | Direct source neurons | Summed contacts |
| --- | --- | ---: | ---: |
| LC4 | Left | 54 | 382 |
| LC4 | Right | 50 | 431 |
| LPLC2 | Left | 94 | 468 |
| LPLC2 | Right | 95 | 622 |

All these exported edges have the processed model sign +1. That is not
measured physiological efficacy or proof that bilateral population activation
equals a looming stimulus. Some annotated neurons have no direct GF edge;
we do not drop them or invent connections.

Reproduce:

```bash
python3 scripts/datasets.py fetch flywire-annotations-630-v1.1.0 \
  --asset Supplemental_file1_annotations.tsv --data-dir "$FLY_DATA_DIR"
.venv/bin/python scripts/audit_takeoff_circuit.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/takeoff-audit/630-001"
```

The external audit includes every selected ID, annotation status, direct
contact/sign records, and explicit `takeoff_ready: false`. Identity/edges
are now verified; looming encoding, electrical/VNC transmission, muscles,
and physical takeoff remain separate unmet gates.

An [artificial-activation probe](../scripts/probe_takeoff_circuit.py) is
available to test no input, LC4, LPLC2, and combined bilateral populations at
100 Hz through the original network. It records actual GF spikes/times,
not body motion. This rate is a diagnostic assumption, not a fitted
looming response; its results must not be described as natural takeoff.

### Artificial population probe result

The complete original model was run for one second per condition, resetting
to seed 420 each time and using independent 100 Hz Poisson input for every
selected input neuron:

| Artificially activated population | Right GF spikes | Left GF spikes | Total network spikes |
| --- | ---: | ---: | ---: |
| None | 0 | 0 | 0 |
| LC4 (104 neurons) | 84 | 82 | 19,480 |
| LPLC2 (210 neurons) | 147 | 128 | 40,151 |
| Both (314 neurons) | 174 | 152 | 57,925 |

GF spike timestamps are saved in the external probe report. No spike
rate/output was fabricated; the unmodified upstream `run_trial` generated
the activity. The first compilation of many individual Poisson input
objects took several minutes; this is not a real-time performance result.

Reproduce:

```bash
.venv/bin/python scripts/probe_takeoff_circuit.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/takeoff-audit/probe-001"
```

This establishes that the audited sensory populations can drive GF activity
in the existing LIF model. It **does not** establish correct natural looming
response curves, spike timing relative to parallel circuits, electrical
motor transmission, or takeoff mechanics. Bilateral uniform-rate activation
is an artificial diagnostic, not retinal perception or a validated stimulus.

The next scientific gate is a controlled looming encoder and comparison
with published GF response timing/interventions. A GF spike must not
automatically switch the body to the trained flight policy.
