# Connectomics research foundation

**Review date:** 2026-10-10  
**Scope:** the five supplied articles, their key primary resources, and
practical preparation for custom simulations.  
**Companion:** [source catalog](../research/sources.json).

The repository now also has a [cross-species catalog and acquisition
guide](dataset-catalog.md). This dossier preserves the initial five-article
research scope; the catalog includes later worm and additional-species
entries with their own review status.

## 1. Executive assessment

### 2026-10-11: embodiment demos versus our integration gaps

- [Eon's primary technical explanation](https://eon.systems/updates/embodied-brain-emulation)
  (S67) describes selected descending outputs influencing modified existing
  NeuroMechFly controllers with hand-chosen gains: oDN1 forward velocity,
  DNa01/DNa02 steering, and selected feeding/grooming outputs. It explicitly
  does not reconstruct the full VNC/motor hierarchy, reports largely missing
  internal-state mechanisms, and says current visual activity does not
  substantially influence behavior. This is substantial multi-behavior
  integration, not recovery of every physiological mechanism.
- [NeuroCraft's primary README](https://github.com/evnsnclr/neurocraft-fly-public/tree/d121466b3ba2f11498e6da498c74acb061bb00eb)
  (S68) explicitly connects neural readouts to scripted Minecraft body programs.
  Runnable mod/companion downloads are not present in that release-status page.
- [FlyGM's selected methods](https://arxiv.org/html/2602.17997) (S69) combine
  a connectome operator with trained encoders, neural updates and motor
  decoders. This differs from our preserved unmodified LIF spike model.

**Project accountability:** missing behavior here is partly incomplete
integration, not universal scientific impossibility. The main body gait uses
a learned comparison reference; verified walking/steering brain outputs have
not been connected to that reference as an end-to-end high-level controller.
Others demonstrate more complete approximate interfaces. Reproducing one of
those brain-influenced interfaces is different from the longer-term target of
measured sensory/VNC/muscle physiology. Every physiological gap need not be
closed before a useful, explicitly labeled reduced interface can be tested.

No external implementation was installed or substituted by this review.
An end-to-end baseline with disclosed decoder assumptions is a useful separate
integration track; it does not erase our failed tests or prove complete autonomy.

The articles describe related but distinct achievements:

1. **FlyWire:** a reconstructed adult **female brain**, with 139,255 neurons
   and approximately 50 million chemical synapses between reconstructed
   neurons. It supplies a mature data ecosystem and a published computational
   modeling baseline. [S01, S04, S06, S14]
2. **MaleCNS:** an adult **male central nervous system**, including central
   brain, optic lobes, ventral nerve cord, and the intact neck connective.
   The paper abstract reports 166,700 neurons and 11,710 neuron types;
   Google reports approximately 125 million synaptic connections.
   Its anatomical scope is especially useful for sensory-to-motor work.
   [S02, S07, S08, S11]
3. **MICrONS:** approximately one cubic millimeter of **mouse visual cortex**,
   not a complete mouse brain. Its distinctive advantage is anatomy and
   functional recordings from the same specimen. [S03, S18, S19]

**Recommendation:** reproduce a bounded FlyWire/Brian 2 experiment first,
then use MaleCNS for a selected sensory-to-motor circuit. Treat MICrONS as a
separate structure/function validation track. Do not begin by downloading
petabytes of images or attaching an unvalidated whole-brain model to a game.

This is a research synthesis, not a reproduction result. Article text,
dataset descriptions, selected upstream code, and bibliographic abstracts
were reviewed. Full primary-paper methods, authenticated queries, downloaded
data contents, and simulator execution have not yet been verified.

## 2. Review of the five starting articles

| Article | Main contribution | Technical relevance | Interpretation limit |
| --- | --- | --- | --- |
| NIH Research Matters, 2024-10-22 [S01] | Whole female fly brain, cell typing, projectome, and information-flow examples | Good overview of neuron/region organization; points to the flagship and annotation papers | "Largest to date" is a historical statement, not a current universal ranking |
| Google Research, 2026-09-03 [S02] | Complete male CNS and AI reconstruction methods | Brain-to-nerve-cord continuity, male/female comparisons, reconstruction tools | Reconstruction AI is not a neural dynamics model; "largest" depends on metric |
| Smithsonian, April 2025 coverage [S03] | MICrONS anatomy plus visual physiology | Motivates testing models against measured activity, not just plausible motion | 200,000 cells are not 200,000 neurons with matched functional data |
| NINDS director's message, 2024 context [S04] | FlyWire consortium, proofreading, neurotransmitter annotations, and projectome | Explains data provenance and human verification | Describes the same female FlyWire achievement as NIH, not a separate dataset |
| 36kr Minecraft account, September 2026 context [S05] | Claimed MaleCNS-to-Minecraft demo by Evan Smith | Illustrates neural dynamics, sensory encoding, and motor decoding interfaces | Says code/mod would be released later; does not establish reproducibility or biological fidelity |

The Google page's simplified text extraction omitted important sections.
The full HTML was separately parsed to review the male CNS statistics,
publication date, vertebrate discussion, and linked resources.

### The Minecraft claim requires a separate evidence standard

The 36kr article attributes the Minecraft demo to Evan Smith. Eon Systems
appears as a comparison to an earlier FlyWire/MuJoCo demonstration, **not**
as the author of the Minecraft project. [S05]

The report says its code was not public at publication. We did not locate
and inspect a released implementation in this review. Consequently:

- The dataset's existence is independently supported; the demo's wiring,
  dynamics, runtime, and sensory/motor mapping are not independently verified.
- Visible motion does not demonstrate that all neurons participate in a
  causal closed loop, or that the motion resembles a real fly.
- The article's proposed LIF approach is not proof that the demo uses that
  implementation.
- A claim of implementation in two days is not a resource estimate for a
  reproducible scientific simulation.
- Neither animation nor a connectome establishes consciousness or complete
  brain emulation.

## 3. Dataset comparison and count reconciliation

| Property | FlyWire female brain | MaleCNS v1.0 | MICrONS cortical volume |
| --- | --- | --- | --- |
| Species/scope | Adult female Drosophila brain | Adult male Drosophila brain plus VNC | P87 mouse; V1 and higher visual areas LM, AL, RL |
| Neurons | 139,255 in flagship paper | 166,700 in paper abstract | Approximately 120,000 anatomical neurons |
| Other counts | Approximately 50 million chemical synapses between reconstructed neurons | 11,710 neuron types; approximately 125 million synaptic connections in Google report | Approximately 200,000 anatomical cells; 75,902 estimated functional neurons from 115,372 functional ROIs |
| Functional data | Not paired whole-brain physiological recordings | Not paired whole-CNS physiological recordings | Calcium responses, stimuli, and behavioral measures; anatomical/functional matches for a subset |
| Initial access | Static Zenodo files; Codex; fafbseg/CAVE tooling | Static cloud files; neuPrint; Clio; navis | CAVE annotations; cloud-volume; DataJoint or NWB functional data |
| Main modeling advantage | Existing published LIF baseline | Intact brain-to-VNC pathways | Same-specimen structure/function tests |
| Main limitation | Brain is not the full CNS/body | Anatomy still does not determine dynamics or biomechanics | Severed volume boundaries and incomplete functional matching |

Sources: [S06, S07, S08, S12, S13, S18, S19, S20, S21, S23].

### Counts that must not be mixed

- **Synapses vs graph edges:** many synaptic contacts can connect one directed
  neuron pair. Neither a 50-million-synapse nor a 125-million-synapse headline
  determines the number of aggregated neuron-pair edges.
- **FlyWire raw vs proofread subsets:** the static release describes roughly
  130 million synapse records, including partners outside the proofread
  neuron set. The headline approximately 50 million refers to connections
  between the reconstructed/proofread neurons. These are different scopes,
  not a discrepancy to repair by arbitrary filtering. [S06, S12]
- **Mouse cells vs neurons vs functional ROIs:** non-neuronal cells count
  toward the approximately 200,000 cells. Functional ROIs are not unique
  neurons; not every recorded neuron has a validated anatomical match.
  [S18]
- **MICrONS 523 vs 524 million:** the portal reports more than 523 million;
  NIH reports more than 524 million. Preserve the source/version distinction
  and derive exact counts from the chosen materialization. [S18, S19]
- **Female brain vs female CNS:** Google's 2026 article also links a newer
  complete female brain-and-nerve-cord resource. Do not assume the older
  FlyWire female brain is the only female dataset, or merge datasets without
  specimen and correspondence checks. The newer paper remains a follow-up
  reading item here. [S02, S25]
- **MaleCNS is not simply MANC:** a male ventral-nerve-cord-only resource and
  the full MaleCNS release are not interchangeable identifiers.

### Primary-source discrepancy: MaleCNS cell typing

The Janelia project page reports **262 sex-specific and 114 sexually dimorphic
types**. The 36kr account repeats those numbers, describing the first group
as male-specific. [S05, S08]

The published paper's indexed abstract instead reports **8,069 isomorphic,
138 dimorphic, 289 male-specific, and 71 female-specific types**, alongside
11,710 types across the CNS. [S07]

Record both with their contexts. Do not combine them or infer that the
difference is explained by a particular taxonomy revision without checking
the full methods, supplements, and release annotations. Prefer the
published abstract when describing what the paper reports, but retain this
as an unresolved scope/version question.

Dates also have different meanings: official release notes put MaleCNS
v0.9 at **2025-10-05** and v1.0 at **2026-06-08**; Google announced the work
on **2026-09-03**, while Europe PMC indexes first publication as
**2026-09-01**. A news date is not a dataset release date. [S02, S07, S10]

## 4. Data access and what to collect

### 4.1 FlyWire: an accessible first baseline

Use the static [Zenodo connectivity record][S12] for public version **783**.
The [annotation repository][S13] warns that annotations changed after the
original publication; pin a tagged release or commit rather than `main`.
Codex annotations can differ from the systematic repository annotations.

Selected files, from Zenodo metadata checked on 2026-10-10:

| File | Bytes | Purpose |
| --- | ---: | --- |
| `proofread_root_ids_783.npy` | 1,114,168 | Proofread neuron identifier set |
| `proofread_connections_783.feather` | 852,022,274 | Aggregated directed connectivity, with neuropil breakdown |
| `flywire_synapses_783.feather` | 9,492,998,242 | Individual synapse locations, partners, and transmitter probabilities |
| `per_neuron_neuropil_count_post_783.feather` | 233,843,050 | Postsynaptic counts per neuron/neuropil |
| `per_neuron_neuropil_count_pre_783.feather` | 16,853,770 | Presynaptic counts per neuron/neuropil |

The first two are a practical initial acquisition; add transmitter and cell
annotations for signed models. Exact filenames, sizes, and upstream MD5
checksums are stored in the catalog. Nothing was downloaded locally.

Important columns:

- Synapse table: `pre_pt_root_id`, `post_pt_root_id`, `cleft_score`,
  `connection_score`, `neuropil`, pre/post positions, and probabilities for
  `gaba`, `ach`, `glut`, `oct`, `ser`, `da`.
- Proofread connection table: presynaptic and postsynaptic root IDs,
  `neuropil`, `syn_count`, and transmitter probability averages.
- Release filtering: the record describes a cleft-score threshold of 50;
  it explicitly says `connection_score` was not used to threshold the
  released analyses. Record these separately from any custom filters.
- Coordinates in this synapse export are **nanometers**. Other interfaces
  may use voxel coordinates; never assume identical units.
- Proofread connections have one row per neuron pair **and neuropil**.
  Aggregate those disjoint neuropil rows when building a pair-level graph;
  preserve the breakdown separately.
- Treat root IDs as opaque identifiers. Preserve exact 64-bit values or
  strings across JSON/JavaScript boundaries; do not round through floating
  point or assume IDs remain stable after segmentation edits.

Use [fafbseg's connectivity documentation][S17] for programmatic work.
Pin dataset and materialization together. [Codex][S26] currently requires a
Google sign-in for computed features; static public downloads avoid that
requirement. Do not assume public data means anonymous access to every API.

The record's suggested Feather "streaming" example first reads an Arrow
table and then slices it. That is not, by itself, a guarantee of bounded
memory for the full file. Verify actual peak memory or use batch-capable
reading/conversion before processing the 9.49 GB synapse table. [S12]

### 4.2 MaleCNS: full sensory-to-motor anatomical scope

Pin the neuPrint dataset to **`male-cns:v1.0`**. The [official download
page][S09] supports both:

- **neuPrint API:** free account and authorization token; Python
  `neuprint-python`, or R `neuprintr`.
- **Public bulk files:** cloud URLs, including aggregated connectivity,
  annotations, body-level transmitter predictions, synapse points,
  partner relationships, and presynaptic-site transmitter predictions.

Base location:

```text
gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/
```

Priority files:

1. `body-annotations-male-cns-v1.0-minconf-0.5.feather`
2. `body-neurotransmitters-male-cns-v1.0.feather`
3. `body-stats-male-cns-v1.0-minconf-0.5.feather`
4. `connectome-weights-male-cns-v1.0-minconf-0.5.feather`

Later, if spatial or contact-level analysis requires it:

5. `syn-points-male-cns-v1.0-minconf-0.5.feather`
6. `syn-partners-male-cns-v1.0-minconf-0.5.feather`
7. `tbar-neurotransmitters-male-cns-v1.0.feather`

The connectivity file responded to an anonymous HTTP HEAD request with
**200 OK** and **1,051,241,946 bytes**. This verifies availability and
declared size, not its row count or contents. The catalog includes the
direct HTTPS URLs published by the project.

The EM and proofread segmentation volumes are **8 nm isotropic**; nuclei
segmentation is 16 nm and the listed brain/VNC region volumes are 256 nm.
Those resolutions apply to different volumes, not to a single shared array.
Morphology can be accessed through navis; inspect units and template
transforms before combining spatial data. [S09]

**API correctness hazard:** the official page's example names the return
values of `fetch_adjacencies` as if the connection table were first.
The API documentation defines the result as **neuron table, connection
table**. Use the pinned client's documented contract, and validate columns
rather than trusting example variable names. Its per-ROI outputs can also
double-count when non-primary overlapping ROIs are included. Use pair-total
outputs when appropriate; do not sum overlapping region hierarchies. [S16]

The official R1-R6-to-DNg13 visualization is useful for selecting a
visuomotor pathway. A path through the graph is not sufficient to define a
validated optical encoder, a causal circuit, or a motor-to-muscle controller.
Confirm cell classifications rather than assuming every "motor" label in
coverage refers to a direct muscle-innervating neuron. [S08]

### 4.3 MICrONS: matched anatomy and function

The [official portal][S18] describes a **1.4 x 0.87 x 0.84 mm** volume:
approximately **1.023 mm3**, covering all six cortical layers and four
visual areas. Functional data are estimates for 75,902 neurons from
115,372 ROIs; anatomical matches are available for a subset.

Access routes:

- [Official tutorials][S20] and [Python tools overview][S21] for CAVEclient,
  cloud-volume, MeshParty, and annotation queries.
- [Tutorial source repository][S22] for maintained environments and
  executable examples.
- [Functional database access][S23]: DataJoint/MySQL, currently documented
  as version **v8**, with companion matching/analysis notebooks.
- [DANDI dataset 000402][S24]: NWB functional recordings, linked by the
  official tools guide. Pin a published version and selected assets before
  acquisition; draft metadata is mutable.

Do not immediately install the full functional database. Its guide lists
more than **120 GB** free disk for the container route, around **222 GB**
during initial image loading, or roughly **115 GB** for SQL ingestion and
around **230 GB** transiently. Prefer selected assets or hosted queries for
the initial experiment. These are upstream requirements, not measurements
of this machine. [S23]

Preserve functional-unit-to-anatomical-root mappings, matching method,
confidence, coordinate transform, and version. A spatially nearby nucleus
is not automatically the same measured neuron.

Boundary inputs are essential: this tissue volume receives signals from
outside itself. A closed isolated simulation of its internal edges is not
a faithful model of the intact cortex. Calcium traces also have indicator
kinetics and noise; compare simulated spikes through an observation model
or appropriately calibrated inferred rates, not directly as identical
signals.

## 5. Existing model: the strongest starting point

[Shiu et al., Nature, 2024][S14] presents a LIF model driven by connectivity
and predicted neurotransmitter identity. Its abstract reports experimentally
tested predictions for taste processing, feeding initiation, and antennal
grooming.

The [reference repository][S15] provides activation/silencing experiments,
notebooks, and Brian 2 code. Baseline revision inspected:

```text
91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
```

The README says the original setup uses **FlyWire 630** and gives separate
configuration paths for **783**. Do not equate updating input filenames with
reproducing the paper's original network.

### Parameters observed in upstream code

| Parameter | Default |
| --- | --- |
| Resting and reset voltage | -52 mV |
| Spike threshold | -45 mV |
| Membrane time constant | 20 ms |
| Synaptic-state decay | 5 ms |
| Refractory period | 2.2 ms |
| Transmission delay | 1.8 ms |
| Scale per signed synaptic count | 0.275 mV |
| Default first/second activation rates | 150 Hz / 0 Hz |
| Poisson input scaling factor | 250 |
| Trial duration / number of runs | 1,000 ms / 30 |

The source uses a decaying voltage-valued synaptic state, with membrane
voltage driven toward resting potential plus that state. These are modeling
choices, not measurements of each reconstructed neuron. Stimulated neurons
have special refractory handling in the implementation.

The upstream input is already processed: connectivity includes
`Presynaptic_Index`, `Postsynaptic_Index`, and
`Excitatory x Connectivity`. A raw FlyWire or MaleCNS table is **not**
a drop-in replacement. Reproduce identifier indexing, transmitter/sign
assignment, filtering, aggregation, and scaling explicitly.

The model's output is spike timing/rates. The upstream README describes
silencing broadly; the inspected helper zeroes outgoing synaptic weights.
Confirm the exact intervention semantics from code when reproducing or
extending experiments. Do not silently change them to incoming-and-outgoing
disconnection.

No simulator was run in this review. Selected source inspection is not a
compatibility or performance validation. Use the original environment
specification as a reproduction starting point, then test any modernization
as a separate change.

## 6. What a connectome does not provide

| Required layer | Data contribution | Additional modeling needed |
| --- | --- | --- |
| Network topology | Directed contacts and regional organization | Filtering, missing partners, version consistency |
| Synaptic influence | Contact counts and transmitter predictions | Receptor-dependent sign, efficacy, decay, delay |
| Neuronal dynamics | Morphology and cell-type labels | Thresholds, time constants, adaptation, intrinsic activity |
| Sensory encoding | Sensory cell/pathway annotations | Optics, receptive fields, stimulus-to-neuron mapping |
| Motor decoding | Descending/VNC/motor connectivity | Muscle activation, joints, mechanics, control latency |
| Learning/state | Anatomical constraints | Plasticity, neuromodulation, behavioral state |
| Evaluation | Published experiments or MICrONS recordings | Observation models, held-out tests, uncertainty |

A transmitter label does not universally determine excitation/inhibition.
In particular, do not import mammalian "glutamate always excites" assumptions
into fly circuits, or reduce dopamine, serotonin, and octopamine to fixed
fast excitatory weights without an explicit justified simplification.
Prediction probabilities should remain available for sensitivity analysis.

A brain/CNS map is not the entire peripheral nervous system, muscle system,
or body. A plausible animation can arise from a hand-designed decoder even
when its internal neural dynamics are incorrect.

## 7. Proposed simulation-ready data contract

This is a design recommendation, not an implemented schema.

**Dataset provenance**

- Species, sex, specimen, anatomical scope, source URL/DOI.
- Release/materialization, annotation revision, download time, license.
- Original filenames, byte sizes, checksums, transformations, and filters.

**Neuron table**

- Opaque source identifier and contiguous simulation index, with a bijection.
- Cell type/class, side, neuropil/region membership, proofread status.
- Transmitter probabilities and label provenance.
- Optional morphology/position with coordinate system and units.

**Directed edge table**

- Source and target indices; measured contact count.
- Optional region breakdown and contact locations.
- Separate modeled weight, sign rule, delay, and uncertainty.
- Declared treatment of self-connections, unidentified partners, and
  excluded neurons. Missing data must not silently become biological zero.

**Experiment record**

- Input and readout cell IDs, stimulus protocol, intervention semantics.
- Equations, parameters, solver/time step, seeds, software revisions.
- Spike times/rates; runtime, peak memory, output size.
- Validation targets and tolerances chosen before interpreting results.

Keep immutable raw exports separate from derived tables and results. Store
large assets outside Git; save manifests rather than opaque local paths.

## 8. Compute and storage planning

These are calculations and engineering recommendations, not benchmarks.

- A dense float32 matrix for 139,255 neurons is approximately **77.6 GB**
  decimal; for 166,700 neurons, approximately **111.2 GB**. Avoid dense
  whole-brain adjacency matrices.
- A minimal edge array with two uint32 simulation indices and one float32
  weight costs **12 bytes per aggregated edge**, before delays, metadata,
  sparse row pointers, event queues, or simulator overhead.
- Thus, a hypothetical 50 million **edges** would require 600 MB for those
  three arrays alone. This is not an estimate that FlyWire actually has
  50 million aggregated edges; its headline is a synapse count.
- File size is not peak memory. Arrow decoding, joins, pandas copies,
  compiled simulator state, parallel workers, and full spike monitors can
  multiply memory requirements.
- The 1.6 PB MICrONS headline refers to the broader imaging/reconstruction
  effort, not a minimum download for a circuit experiment.
- Begin with selected circuits and sparse exports. Measure wall time,
  peak resident memory, spikes/events, and simulated-seconds per wall-second
  before choosing workstation or GPU requirements.
- Brian 2's upstream README discusses C++ code generation for performance.
  GPU acceleration and real-time execution remain unverified here.

## 9. Recommended first experiments and acceptance gates

### A. Reproduce one published FlyWire experiment

Choose a taste-to-feeding or mechanosensory-to-grooming experiment from the
upstream notebooks. Preserve its dataset version and interventions.

Acceptance gates:

1. Exact neuron-ID mapping and complete referenced input/readout sets.
2. Reconstructed counts and weights agree with the selected source export.
3. Fixed configuration and seeds reproduce results; stochastic trials are
   summarized with uncertainty rather than a single animation.
4. Match the selected publication/notebook target with declared tolerances.
   Those numerical targets must be extracted during reproduction, not
   invented in this review.
5. Record runtime and memory; silence/shuffle controls test whether topology
   is responsible for the result.

### B. Build a bounded MaleCNS sensory-to-motor hypothesis

Inspect the official visuomotor pathway or another annotated circuit.
Retain necessary recurrent partners and account for excluded boundary inputs.
Do not assume a shortest path is a sufficient simulation.

Begin with synthetic sensory drive and neural readouts. Only then add an
encoder and motor decoder. Validate anatomical path identity, expected
response direction, intervention effects, timing, and robustness to weight/
delay uncertainty before attaching a physics engine.

### C. Use MICrONS for a structure/function benchmark

Select a well-characterized set of anatomically matched functional neurons.
Pin the CAVE and functional-data versions and matching confidence.
Predict held-out stimulus responses, compare against rate/calcium
observations using an appropriate observation model, and compare with
non-connectomic and shuffled-connectivity baselines.

This asks whether anatomy improves prediction, not whether a cortical
fragment independently recreates mouse vision.

## 10. Licensing, provenance, and remaining work

Verified:

- FlyWire Zenodo connectivity record: **CC BY 4.0**, open access. [S12]
- MaleCNS project download page: **CC BY 4.0**. [S09]
- Published fly-model software: GitHub metadata reports **MIT**. [S15]

Not yet verified for redistribution:

- Licenses of every annotation, auxiliary morphology asset, MICrONS
  structural/functional export, and dependency.
- MICrONS is described as open access, but this review did not establish a
  single license covering all assets. The queried DANDI draft version
  summary did not provide a license field; consult its asset/version
  metadata and terms rather than assuming absence of restrictions.
- Article text and figures are not automatically covered by dataset
  licenses. This repository stores original summaries and references, not
  mirrored articles.

Next research priorities:

1. Full methods/supplement review for the three main connectomes and the
   published LIF model, including confidence filters and exact weight rules.
2. Resolve MaleCNS type-count differences against final annotations.
3. Evaluate the newer female CNS resource for comparison and embodiment.
4. Verify selected MICrONS asset licenses and anatomical/functional matching.
5. Locate any subsequently released Minecraft/Eon implementation and audit
   its sensor/controller boundary before using it as a baseline.
6. Obtain explicit storage/compute limits and choose the first biological
   experiment before downloading data or installing simulator dependencies.

Access notes: some publisher pages returned HTTP 406 or 403; indexed
abstracts and official project resources were used instead. A transient
Zenodo API failure was retried successfully. Several guessed documentation
paths returned 404; the working official tutorial root is recorded below.
Do not treat inaccessible full methods as reviewed.

## Source index

IDs match the [machine-readable catalog](../research/sources.json).

- [S01: NIH female fly overview][S01]
- [S02: Google male CNS announcement][S02]
- [S03: Smithsonian MICrONS coverage][S03]
- [S04: NINDS FlyWire context][S04]
- [S05: 36kr Minecraft account][S05]
- [S06: Dorkenwald et al. female brain paper][S06]
- [S07: MaleCNS paper bibliographic record][S07]
- [S08: Janelia MaleCNS project][S08]
- [S09: MaleCNS download documentation][S09]
- [S10: MaleCNS release notes][S10]
- [S11: MaleCNS project portal][S11]
- [S12: FlyWire static connectivity release][S12]
- [S13: FlyWire systematic annotations][S13]
- [S14: Shiu et al. computational-model paper][S14]
- [S15: Computational-model source repository][S15]
- [S16: neuprint-python API documentation][S16]
- [S17: fafbseg connectivity documentation][S17]
- [S18: MICrONS cubic-millimeter portal][S18]
- [S19: NIH MICrONS announcement][S19]
- [S20: MICrONS tutorials][S20]
- [S21: MICrONS Python/data-access tools][S21]
- [S22: MICrONS tutorial source][S22]
- [S23: MICrONS functional database access][S23]
- [S24: DANDI functional-data archive][S24]
- [S25: Newer female CNS paper, follow-up only][S25]
- [S26: Codex access page][S26]
- [S27: FlyWire project and provenance][S27]
- [S28: MICrONS flagship paper, linked via portal][S28]

[S01]: https://www.nih.gov/news-events/nih-research-matters/complete-wiring-map-adult-fruit-fly-brain
[S02]: https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/
[S03]: https://www.smithsonianmag.com/smart-news/in-a-world-first-researchers-mapped-part-of-a-mouses-brain-in-incredible-detail-its-a-leap-forward-for-neuroscience-180986406/
[S04]: https://www.ninds.nih.gov/news-events/directors-messages/all-directors-messages/brain-initiative-researchers-complete-groundbreaking-map-fly-brain
[S05]: https://eu.36kr.com/en/p/3971642393686535
[S06]: https://doi.org/10.1038/s41586-024-07558-y
[S07]: https://doi.org/10.1016/j.cell.2026.08.015
[S08]: https://www.janelia.org/project-team/flyem/male-cns-connectome
[S09]: https://male-cns.janelia.org/download/
[S10]: https://male-cns.janelia.org/release/
[S11]: https://male-cns.janelia.org/
[S12]: https://zenodo.org/records/10676866
[S13]: https://github.com/flyconnectome/flywire_annotations
[S14]: https://doi.org/10.1038/s41586-024-07763-9
[S15]: https://github.com/philshiu/Drosophila_brain_model
[S16]: https://connectome-neuprint.github.io/neuprint-python/docs/queries.html
[S17]: https://fafbseg-py.readthedocs.io/en/latest/source/tutorials/flywire_connectivity.html
[S18]: https://www.microns-explorer.org/cortical-mm3
[S19]: https://www.nih.gov/news-events/news-releases/scientists-map-unprecedented-detail-connections-visual-perception-mouse-brain
[S20]: https://tutorial.microns-explorer.org/
[S21]: https://tutorial.microns-explorer.org/python-tools.html
[S22]: https://github.com/AllenInstitute/microns_tutorial
[S23]: https://github.com/cajal/microns-nda-access
[S24]: https://dandiarchive.org/dandiset/000402
[S25]: https://www.nature.com/articles/s41586-026-10735-w
[S26]: https://codex.flywire.ai/api/download
[S27]: https://flywire.ai/
[S28]: https://doi.org/10.1038/s41586-025-08790-w
