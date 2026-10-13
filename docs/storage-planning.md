# Storage planning for projects that can be completed

**Checked:** 2026-10-10. Sizes use decimal units: MB = 1,000,000 bytes,
GB = 1,000,000,000 bytes, TB = 1,000 GB, PB = 1,000 TB.
These differ from MiB/GiB shown by some operating-system tools.

## The important distinction: complete connectivity vs every raw asset

For many simulation projects, "full dataset" should mean the complete
**selected connectivity release plus necessary annotations**, not every
electron-microscope image, segmentation volume, mesh, intermediate
reconstruction, and functional recording.

A point-neuron network can use connectivity and assumed dynamics without
storing every raw image. Detailed multicompartment models, morphology
analysis, or new reconstruction work may require additional spatial data.
Acquire those only when the project needs them.

No data size guarantees completion: data coverage, physiological assumptions,
scientific acceptance criteria, RAM, and runtime matter independently.
Smaller worms are easier to inspect computationally, but their complete
behavior is not automatically determined by their wiring.

## Verified input sizes

These are provider-declared file sizes, not local downloads or benchmarks.
Sources and selected assets are recorded in
[the source catalog](../research/sources.json).

| Input selection | Declared size | What it includes / excludes |
| --- | ---: | --- |
| Corrected C. elegans workbook | 4.19 MB | Adult hermaphrodite/male connectivity matrices; not every image or physiological parameter |
| Pinned C. elegans calcium activity Parquet | 669.51 MB | Processed per-neuron GCaMP traces from 12 source datasets; not raw imaging movies or action-potential trains |
| Published fly-model processed inputs, version 630 | 89.69 MB | Completeness CSV + processed connectivity Parquet used by upstream default configuration |
| Published fly-model processed inputs, version 783 | 104.13 MB | Alternative public-version CSV + processed connectivity Parquet; changing versions is not reproducing the original network |
| FlyWire 783 proofread roots + connections | 853.14 MB | Proofread IDs and neuron-pair/neuropil connectivity; add necessary transmitter/cell annotations |
| FlyWire 783 five cataloged products | 10.60 GB | Roots, connections, full released synapses, and two regional count tables; not all FlyWire assets |
| MaleCNS core annotations + transmitter labels + weights | 1.11 GB | Three files useful for a point-neuron network; exact transformations still need review |
| MaleCNS seven cataloged flat files | 24.38 GB | Core plus body statistics, synapse points, partners, and presynaptic-site transmitter predictions |
| Entire listed MaleCNS flat-connectome prefix | 31.32 GB | Eleven objects, including alternate filtered weights/partners; these overlap and need not all be fetched |

The five FlyWire products, seven selected MaleCNS files, corrected worm
workbook, and selected worm activity Parquet together occupy
**35,647,950,409 bytes (~35.65 GB)** before adding other annotations,
environments, conversions, results, or backups.
That is **not** a total for all seven species.

### MaleCNS inventory

The provider's public
[object metadata API](https://storage.googleapis.com/storage/v1/b/flyem-male-cns/o?prefix=v1.0%2Fconnectome-data%2Fflat-connectome%2F&fields=items(name,size,md5Hash),nextPageToken)
returned eleven objects and no next-page token. The seven selected files:

| File role | Bytes |
| --- | ---: |
| Body annotations | 14,483,314 |
| Body neurotransmitters | 43,282,834 |
| Body statistics | 778,062,826 |
| Unrestricted minconf-0.5 connectome weights | 1,051,241,946 |
| Synapse points | 13,061,489,098 |
| Synapse partners | 6,777,179,098 |
| T-bar neurotransmitters | 2,651,680,218 |

Sizes and MD5 values from provider metadata are now stored in the catalog.
No data-file contents were transferred or inspected. The alternate
`significant-only` and `traced-only` exports account for the difference
between 24.38 GB and the full 31.32 GB prefix.

### Published fly-model inputs

The [reference model repository](https://github.com/philshiu/Drosophila_brain_model)
contains compact, already processed inputs. At the inspected revision:

- Version 630: 3,057,611-byte completeness CSV and 86,630,944-byte Parquet.
- Version 783: 3,327,347-byte completeness CSV and 100,804,642-byte Parquet.

This is a useful first-project baseline, not a claim that all fly data fit
in 104 MB. Its sign/indexing/filter transformations need to be understood
and preserved. Its README also notes several GB of archived model outputs.
Those outputs are separate from the compact inputs.

## Working-space budgets

The following are **planning allocations**, not measured requirements or
guarantees. They include room for dependencies, one working conversion,
bounded results, and temporary files. Increase them when experiments,
retained releases, morphology, or backups grow.

| Project track | Suggested free working space | Realistic initial target |
| --- | ---: | --- |
| C. elegans connectivity project | 5-10 GB | Graph exploration or a small, explicitly parameterized neural/body experiment |
| Published fly-model reproduction | 20-50 GB | One feeding/grooming activation or silencing experiment |
| FlyWire complete listed synapse products + derived work | 50-100 GB | Connectivity-driven circuit analysis and bounded simulation batches |
| FlyWire + selected MaleCNS products | 100-200 GB | Both fly maps, processing space, and controlled result retention |
| MICrONS selected circuit/recording queries | 20-100 GB allocation | Bounded anatomy/function comparison; selected assets determine actual size |
| MICrONS full local functional database plus selected structure | 300-500 GB allocation | Local physiological analysis, not the full imaging reconstruction |
| Human H01 selected cells/circuit | 20-100 GB allocation | Proofread morphology/circuit analysis; not whole-human-brain simulation |
| Tunicate / annelid projects | Not established | Pin and size individual files before setting a budget |
| Zebrafish Fire&Wire | Not established | Verify access terms, release snapshot, and selected asset inventory first |

The upstream [MICrONS database guide](https://github.com/cajal/microns-nda-access)
documents more than **120 GB** for the container route, with about
**222 GB** during initial loading. The SQL route lists **115 GB** and about
**230 GB** transiently during ingestion. The 300-500 GB allocation leaves
additional room for selected structural exports, queries, and results.
It does not include the complete structural archive.

Project examples for the partial mammalian maps include connectivity
statistics, cell morphology, circuit models, and structure/function
prediction. They are not equivalent to recreating an entire mouse or human.

## Raw imaging archive scale

- **MICrONS:** NIH describes **1.6 PB** of data collected for the cortical
  reconstruction effort. That headline is not a verified downloadable
  manifest total or a prerequisite for using selected circuit data.
  [NIH source](https://www.nih.gov/news-events/news-releases/scientists-map-unprecedented-detail-connections-visual-perception-mouse-brain)
- **Human H01:** the official release describes a **1.4 PB** tissue volume.
  It is still only a small cortical sample, not a whole human brain.
  [H01 source](https://h01-release.storage.googleapis.com/landing.html)
- Full fly imaging/segmentation archive sizes have **not** been inventoried
  here. Do not infer them from the much smaller connectivity tables.

For perspective, 1.4 PB is approximately **1,400 TB**. Mirroring the
mammalian imaging resources is a dedicated storage/infrastructure undertaking,
not an appropriate first step for this repository.

## Practical recommendation

1. **Start with 50-100 GB free** for a bounded worm or fly-model project.
   A worm-only project can begin with considerably less.
2. **Reserve around 250 GB free** for a comfortable worm-plus-both-fly
   working collection with controlled outputs and revisions.
3. **A 1 TB SSD is a convenient growth option**, not a minimum or a guarantee
   of fitting future archives. Consider more space only after selecting
   MICrONS/human assets or other releases.
4. Keep raw imaging in provider storage and fetch required regions/files.
   Account separately for backups and multiple retained releases.

Use approximately **2-3 times the selected stored input size** as an initial
conversion/headroom heuristic, then add the environment and measured result
retention budget. Actual peak use can be larger: a Feather-to-Parquet
conversion, indexing job, database ingest, or dense export may create more
than one temporary copy.

For the worm/fly tracks, large result streams can eventually exceed the
inputs. Prefer spike events and selected readouts to recording every neuron's
state at every time step. Estimate output bytes before a long run and keep
the source version, parameters, seeds, and acceptance results with each run.

Disk is separate from RAM: a 1 GB input file may require much more memory
after decoding, indexing, and simulator allocation. Benchmark a small run
before choosing CPU/GPU hardware or promising real-time whole-brain behavior.

## Before acquiring project data

- Choose the experiment and objective completion criteria.
- Agree on an external data directory and transfer/storage budget.
- Pin source code, dataset snapshot, and required annotations.
- Check asset size, checksum, license, and any access restrictions.
- Plan temporary conversions, output retention, and backup space.
- Acquire only those assets; validate the first run before scaling.

The user has now selected the mounted XFS volume for the first fly project.
Its [30-trial baseline](../experiments/flywire-sugar/README.md) used roughly
89 MiB of external data/results before replay and a 399 MiB Linux-side
environment, with peak process RAM of about 4.2 GiB. These are measured
figures for one bounded experiment, not requirements for future full-data
analysis or an embodied fly simulation.
