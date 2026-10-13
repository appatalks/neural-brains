# C. elegans microscope connectivity and activity view

This local microscope UI overlays a pinned adult hermaphrodite Cook et al.
connectome with two bounded Kato2015 recorded calcium traces. Start it from
the repository root after setting `WORM_DATA_DIR` to the approved external
data root:

```bash
.venv-worm/bin/python -m pip install -r experiments/worm/requirements.txt
```

Install once in the separate Python 3.13 worm environment. Prepare the external
view bundle and launch it with:

```bash
: "${WORM_DATA_DIR:?Set WORM_DATA_DIR to the approved external data directory}"
.venv-worm/bin/python scripts/worm_data.py \
  --data-dir "$WORM_DATA_DIR" \
  --output "$WORM_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json" \
  --sex hermaphrodite \
  --recording WT_NoStim.mat=worm7 \
  --recording WT_Stim.mat=worm0
python3 scripts/worm_microscope.py \
  --model "$WORM_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json"
```

Open **http://127.0.0.1:8840/**. This is the project's sole interactive port:
the server binds only to loopback, rejects alternate/ephemeral ports, and
fails if 8840 is occupied. Use **Enter fullscreen** in the header; press
**Esc** or use **Exit fullscreen** to return. Close the server with `Ctrl+C`.

## What is wired

- The selected workbook sheets are `hermaphrodite chemical` and corrected
  `hermaphrodite gap jn symmetric`. The audited graph has 473 distinct cell
  labels, 4,879 directed chemical entries and 1,433 undirected gap-junction
  pairs. Chemical self-entries are retained. Seventeen nonzero electrical
  diagonal entries are preserved in audit metadata but excluded from
  self-gap-junction edges.
- Chemical matrices use row = presynaptic cell and column = postsynaptic cell.
  Electrical edges come from the corrected symmetric sheet and appear once
  per undirected pair. Weights are EM serial-section connectivity measures,
  not synaptic conductances or calibrated transmission strengths. The
  workbook includes neurons and other cells/end organs; this adapter does not
  guess cell classes.
- The activity subset is `Kato2015/WT_NoStim.mat/worm7` and
  `Kato2015/WT_Stim.mat/worm0`. It overlays 33 and 40 exactly matched,
  labeled cell traces. Each also has five labeled cells not matching the
  selected matrix, plus 71 and 62 unlabeled trace rows, respectively. These
  remain unmatched/unlabeled rather than being converted to silent neurons.
- Activity comes from the source-provided `original_calcium_data` field.
  Playback advances by sample order and shows the stored timestamp; duplicate
  timestamps are preserved, with no interpolation. Values are calcium
  fluorescence, not membrane voltage or action-potential times.

## Anterior touch → reversal surrogate

**Apply anterior touch pulse** sends a controlled pulse to the `ALML` and
`ALMR` cell labels. The server relays it over the exact selected chemical
edges (forward) and electrical gap edges (bidirectionally), with a fixed
0.5 attenuation per hop and a four-hop bound. It then compares activity on
the real `AVD→VA/DA` and `AVB→VB/DB` structural routes. In the pinned
hermaphrodite matrix, the current relay returns backward score 0.25 vs forward
score 0.125; an example path is `ALML → AVDR → DA01`.

When the assumed decoder selects backward movement, the illustrated body
reverses its kinematic wave for 1.5 simulation seconds. The activity overlay
is not used by this relay. No touch is generated automatically.

The **Activity map** selector switches between recorded calcium fluorescence
and the touch-relay visualization. The latter animates a first-arrival
spanning relay edge per activated cell, by hop, over the measured connectome.
Its 0.12-second-per-hop display pacing is assumed; it is not a spike raster,
complete synaptic event log, or biological latency. Fullscreen expands both
the microscope field and graph for inspection.

This is an **explicit topology-relay surrogate**, not a neural or biomechanics
simulation. It assumes every chemical edge relays positive activation, every
gap edge relays bidirectionally, fixed attenuation and timing, the AVD/AVB
motor-group decoder, and a direct mapping of that decoder to wave direction.
The Cook workbook contains no synaptic signs, conductances, membrane
parameters, or calibrated force-to-receptor encoding. The control button
evokes named touch-cell input; it is not a calibrated physical collision.
No input produces no relay or reversal. On the pinned matrix, removing all
ALML/ALMR-connected edges removes both motor scores; removing AVD-to-VA/DA
outputs removes the backward score and leaves the weaker forward route. These
are structural-surrogate controls, not physiological causation evidence.

The primary [Chalfie et al. 1985 touch-circuit paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6565008/)
abstract reports anterior-touch pathways involving AVD and AVB, inferred from
serial-section reconstruction and assessed with laser ablation. This supports
the pathway identities and behavioral question; it does not validate this
relay's gains, signs, timing, or movement decoder.

The processed activity table does not encode sex or developmental stage per
recording, so the UI does not claim an exact cohort-matched sex/stage. The
Kato fluorescence remains an observational overlay and is not converted to
spikes. Graph placement is schematic, not anatomical. There is no physical
substrate, calibrated muscle model, receptor feedback, spontaneous activity,
or autonomous locomotion.

## Data provenance and terms

The activity Parquet is pinned to Hugging Face commit
`a28aacad1a997ac7aee98f1c52993ab8c0599ee8`, is 669,511,381 bytes, and its
provider SHA-256 is verified. The processed dataset card identifies the
aggregate as MIT-licensed and the table aggregates 12 sources. Only the two
Kato2015 worm recordings listed above are placed in the external derived
bundle; their source and specimen labels are retained.

The 4,188,190-byte corrected Cook workbook has **no established upstream
checksum or explicit asset license**. The user approved local-only evaluation
on 2026-10-12. Its receipt contains a local SHA-256, which is not upstream
verification. Do not redistribute the workbook or derived connectivity.
Both raw assets and generated bundle remain outside Git. See the
[dataset catalog](dataset-catalog.md#worm-specific-distinctions) and
[storage planning](storage-planning.md).

Focused contracts are tested with:

```bash
python3 -m unittest discover -s tests -p 'test_worm*.py'
```
