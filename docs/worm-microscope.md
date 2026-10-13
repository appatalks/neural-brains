# C. elegans microscope connectivity and activity view

This local microscope UI overlays a pinned adult hermaphrodite Cook et al.
connectome with two bounded Kato2015 recorded calcium traces. Start it from
the repository root after setting `FLY_DATA_DIR` to the approved shared external
data root:

```bash
.venv-worm/bin/python -m pip install -r experiments/worm/requirements.txt
```

Install once in the separate Python 3.13 worm environment. Prepare the external
view bundle and launch it with:

```bash
: "${FLY_DATA_DIR:?Set FLY_DATA_DIR to the approved shared external data directory}"
.venv-worm/bin/python scripts/datasets.py fetch openworm-movement-aq2947-20140301 \
  --asset 51_R_1_N2_1_day8_CCW_2014_03_01__19_46_55___7___13.hdf5 \
  --data-dir "$FLY_DATA_DIR" --max-bytes 300000000
.venv-worm/bin/python scripts/worm_data.py \
  --data-dir "$FLY_DATA_DIR" \
  --output "$FLY_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json" \
  --sex hermaphrodite \
  --recording WT_NoStim.mat=worm7 \
  --recording WT_Stim.mat=worm0
.venv-worm/bin/python scripts/worm_microscope.py \
  --model "$FLY_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json" \
  --reference-data-dir "$FLY_DATA_DIR"
```

The fetch command is needed only if the pinned asset is not already acquired;
do not rerun it when the `.download` bundle exists. The viewer verifies the
catalog size, provider MD5 and receipt SHA-256 before opening it.
Open **http://127.0.0.1:8840/**. This is the project's sole interactive port:
the server binds only to loopback, rejects alternate/ephemeral ports, and
fails if 8840 is occupied. Use **Enter fullscreen** in the header; press
**Esc** or use **Exit fullscreen** to return. Close the server with `Ctrl+C`.

## Graphics and display fidelity

The browser renderer adapts the microscope, connectome and trace canvases to
the display pixel ratio (up to 3×, with a per-canvas pixel budget) and expands
the layout on large displays. Lighting, glass falloff, shading and trace
contrast are presentation effects only. The model pane remains a kinematic
illustration on a stylized agar plate; graph positions remain schematic, with
no anatomical coordinates. A separate reference pane shows the pinned
640 × 480-pixel brightfield snapshots and recorded mask outline. No fixed 8K
export or invented image detail is produced; display upscaling does not add
resolution.

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

## Recorded imagery and synthetic foraging experiment

The optional reference pane loads the selected CC-BY-4.0 Open Worm recording
from the external data root. Startup rechecks its catalog-pinned size, Zenodo
MD5, and local SHA-256 receipt. In the HDF5 asset, `full_data` contains 106
actual 640 × 480 brightfield snapshots, saved every 200 mask frames; `mask`
contains 21,163 segmented frames and a recorded source timestamp per frame.
Its FPS metadata reports 31.25 (expected FPS is 30), but timestamps are
nonuniform and include one duplicate; the recording clock spans 898.464 s. The
viewer highlights the tracked-mask outline on the most recent raw snapshot.
That background is held between sparse snapshots: this is not a continuous
raw camera movie, missing pixels are not reconstructed, and motion is not
interpolated. The slider scrubs source frames; review playback is display-paced
at about 10 frames/s, while the original timestamp remains visible. The
recorded animal is AQ2947/N2, an adult day-8 hermaphrodite on OP50/NGM agar in
a 35 mm arena. Zenodo creator metadata lists Celine N. Martineau and Ellen
A. A. Nollen; the embedded description's `who` field also lists Bora
Baskaner. The images are independent of the Kato calcium recordings and are
never used as neural input to the model.

**Start modeled foraging** explicitly enables a separate, assumed loop on the
selected hermaphrodite Cook graph. It renders simulated bacterial patches on
agar—not algae or free-floating organisms, since the selected recording is an
OP50 agar-plate experiment. The assumed odor field encodes left/right cues at
AWA/AWC labels; unsigned chemical and bidirectional gap paths use a fixed
0.5 attenuation for at most four hops; AVB activity is decoded as forward
drive; and close food contact directly produces an MC/M3/NSM feeding-rate
proxy while depleting simulated patch biomass. The rate readouts and
probabilistic event pulses are synthetic, not measured neural activity.
Measured Cook topology is kept distinct from all these assumed signs,
dynamics, sensory encoding, decoding and feeding rules. The visible worm body
is 2D kinematic, not a muscle, proprioception, fluid or organism simulation.
The synthetic field uses a 35 mm-diameter plate matching the source record's
arena metadata; this geometry match does not make the behavioral protocols
equivalent. An explicit 16.3 mm head-position clamp keeps the illustrative
1.05 mm body inside the plate without inventing a neural edge-avoidance
response. Body length and motion remain uncalibrated.

The recorded mask playback, Kato calcium traces and synthetic foraging loop
are three separate data layers. Neither reference recording is synchronized
to the assumed model; calcium fluorescence is not converted to spikes.

A bounded software smoke run on the pinned hermaphrodite graph (seed 420,
0.1 s steps for 60 simulated seconds) reached one simulated patch at 19.4 s,
reported food contact on 31 of 600 steps, and emitted 61,202 synthetic event
pulses. The maximum head radius was 3.14 mm in the 17.5 mm-radius dish, so the
geometric clamp did not activate in this run. These checks confirm the
assumed code path and bounded state only; they are not a measured foraging,
feeding, neural-activity or behavior result.

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
.venv-worm/bin/python -m unittest discover -s tests -p 'test_worm*.py'
```
