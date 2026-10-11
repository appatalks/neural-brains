# Cross-species dataset catalog and acquisition

The initial three species are **C. elegans, Drosophila, and mouse**.
The catalog now also includes primary resources for human, a tunicate,
a marine annelid, and zebrafish. These seven species are a starting collection,
not an exhaustive list of mapped animals.

The first active project is the [FlyWire-630 sugar-to-MN9 reproduction](../experiments/flywire-sugar/README.md).
Its compact original processed inputs are separately cataloged from the
full scientific exports below and have now been acquired externally.

The authoritative machine-readable inventory is
[research/sources.json](../research/sources.json). One species can have many
datasets, specimens, sexes, stages, modalities, and release versions. Keep
these separate: a larval map is not an adult map, and a cortical fragment is
not a whole brain.

See [storage planning](storage-planning.md) for verified download sizes and
working-space allocations before selecting assets.

## Current coverage

| Species | Dataset ID | Coverage | Acquisition status |
| --- | --- | --- | --- |
| Drosophila melanogaster | `flywire-model-630` | Original processed network for published model | Acquired with pinned Git blob checksums; bounded baseline executed |
| Caenorhabditis elegans | `wormwiring-cook2019-corrected2020` | Adult hermaphrodite/male whole-animal nervous-system matrices | Public corrected workbook; checksum/license still to verify |
| Drosophila melanogaster | `flywire-female-brain-783` | Adult female whole brain | Public versioned files, selected upstream checksums |
| Drosophila melanogaster | `male-cns-v1.0` | Adult male brain plus ventral nerve cord | Public bulk files; all seven selected files have provider sizes/MD5 values |
| Mus musculus | `microns-cortical-mm3` | Mouse visual cortical volume, not whole brain | CAVE and functional-data portals; no single asset pinned yet |
| Homo sapiens | `human-h01` | Approximately one cubic millimeter of human cortex | Public cloud/Neuroglancer data; no single asset pinned yet |
| Ciona intestinalis, as named in paper | `ciona-larval-cns-2016` | Larval CNS, 177 neurons | Primary abstract verified; supplements and taxonomy need review |
| Platynereis dumerilii | `platynereis-larval-connectome` | Three-day-old larva whole-body connectome | Lab data/code repository reviewed; individual assets need selection |
| Danio rerio | `zebrafish-fire-and-wire` | Larval whole-brain draft with activity/behavior | Developer terms; no immutable public snapshot verified |

### Worm-specific distinctions

The 1986 C. elegans reconstruction is the historical first landmark animal
connectome. The catalog's initial downloadable workbook instead uses
Cook et al.'s 2019 whole-animal maps, **corrected in July 2020**.

These data include chemical synapses, electrical gap junctions, and
neuromuscular/end-organ connections. Do not collapse them into one ordinary
directed chemical-synapse graph. Multiple workbook sheets and cell classes
must be inspected before conversion to simulation tables.

Sources: [WormWiring](https://www.wormwiring.org/),
[corrected matrices](https://www.wormwiring.org/pages/adjacency.html), and
[Cook et al.](https://doi.org/10.1038/s41586-019-1352-7).

### Additional species: evidence and limitations

- **Human:** [H01](https://h01-release.storage.googleapis.com/landing.html)
  provides reconstructed tissue, synaptic annotations, and a much smaller
  proofread subset. The [data page](https://h01-release.storage.googleapis.com/data.html)
  supplies cloud prefixes and CC BY 4.0 terms. Automated fragments should
  not be presented as a complete human brain.
- **Tunicate:** the [2016 Ciona paper](https://doi.org/10.7554/eLife.16962)
  reports 177 larval CNS neurons. Its indexed abstract was reviewed; the
  exact supplementary matrix, license, and specimen taxonomy remain to
  check.
- **Marine annelid:** the [Jékely lab compendium](https://github.com/JekelyLab/Platynereis_3D_connectome_2024)
  provides data/code for the three-day-old larva and states CC BY 4.0.
  The catalog pins a repository commit. Archive metadata retrieval failed,
  so no guessed archive files have been enabled.
- **Zebrafish:** the [Fish Fire&Wire project](https://www.janelia.org/fish-firewire)
  describes aligned anatomy/activity in a six-day-old larva, with ongoing
  proofreading and developer access terms. The catalog does not claim that
  this is a fully proofread, unrestricted immutable download.

These resources were reviewed at the project/abstract level on 2026-10-10,
not scientifically reproduced. Consult each catalog source's review status.

## Download workflow

### What belongs in Git

Track source code, tests, documentation, dataset manifests, and verified
upstream URLs/version/checksum metadata. Do not track biological dataset
payloads, downloaded archives, or bulk generated results.

The repository's [.gitignore](../.gitignore) excludes `data/`, `downloads/`,
and `results/` directories as a safeguard against accidental additions.
The acquisition tool still requires storage **outside the repository**;
ignore rules do not change that storage boundary.

Do not use `git add -f` to bypass these rules. Git ignore rules do not remove
already tracked files; inspect `git ls-files data downloads results` if
dataset files were previously added. Keep small deliberate test fixtures
under `tests/`, not in an ignored dataset directory.

The versioned catalog and commands below allow another checkout to acquire
the same selected assets without committing the assets themselves. A dataset
is not considered acquired or scientifically validated merely because its
download instructions exist.

The [acquisition tool](../scripts/datasets.py) requires **Python 3.10+**,
without third-party dependencies. It downloads exactly one selected asset
per invocation. Listing and planning never access the network.

### 1. Inspect available species and assets

```bash
python3 scripts/datasets.py list
python3 scripts/datasets.py list --species drosophila-melanogaster
python3 scripts/datasets.py plan flywire-female-brain-783
```

`plan` prints dataset metadata and selected assets. A portal/review-only entry
may have no downloadable assets. It remains cataloged but cannot be fetched
until an exact file URL is added.

### 2. Choose external storage and an explicit asset

For example, this command **will download** the roughly 1.1 MB proofread
FlyWire identifier set:

```bash
python3 scripts/datasets.py fetch flywire-female-brain-783 \
  --asset proofread_root_ids_783.npy \
  --data-dir /mnt/connectome-data
```

Replace the storage path with an existing/writable external location.
Directories inside the repository, including symlink aliases into it, are
rejected. No default storage location is inferred.

The default hard transfer limit is **100,000,000 bytes**. Larger assets
require an explicit higher limit. For example, the following command
**will download** about 852 MB:

```bash
python3 scripts/datasets.py fetch flywire-female-brain-783 \
  --asset proofread_connections_783.feather \
  --data-dir /mnt/connectome-data \
  --max-bytes 900000000
```

The byte cap is checked against known catalog size, server length when
available, and actual streamed bytes. It limits a single transfer, not
expanded dataset size, total disk use, or later analysis memory.

### 3. Handle unavailable upstream checksums explicitly

The worm workbook has a verified public URL and declared size, but we have
not established an upstream checksum or reuse license.

After reviewing source terms, an explicit opt-in allows downloading it:

```bash
python3 scripts/datasets.py fetch wormwiring-cook2019-corrected2020 \
  --asset 'SI 5 Connectome adjacency matrices, corrected July 2020.xlsx' \
  --data-dir /mnt/connectome-data \
  --allow-unverified
```

This flag acknowledges **missing upstream checksum verification only**.
It does not grant permission to reuse/redistribute an asset or imply that its
license is known. The tool prints license metadata and warnings. Never copy
OpenWorm's software license onto unrelated WormWiring data.

### 4. Preserve the bundle and receipt

Successful downloads create:

```text
<external-data-dir>/
  <dataset-id>/
    <filename>.download/
      <filename>
      receipt.json
```

The receipt records source URL, resolved URL, version, license metadata,
source references, download time, expected/actual byte counts, local SHA-256,
and upstream checksum verification status.

- Known size/checksum mismatches, HTTP errors, and HTML login/error pages
  produce explicit failures; temporary files are cleaned up.
- Data are not published until transfer validation completes.
- Existing bundles are never overwritten or implicitly accepted as valid.
  Inspect the receipt and independently verify retained files, or choose a
  different storage root for a new acquisition.
- A local SHA-256 without a known upstream checksum records what was fetched;
  it does **not** prove the source was unchanged.
- No archives are extracted, databases installed, APIs authenticated,
  simulation tables generated, or credentials stored.
- There is no automatic retry/resume or "download everything" option.

Upstream MD5 values are useful for detecting ordinary transfer corruption,
not adversarial authenticity. Preserve receipts, and obtain stronger
published hashes where available.

Pinned upstream Git files can also use `git-blob-sha1` checksums with their
exact size. The downloader hashes the Git blob header and file content,
not plain file SHA-1. These checks establish snapshot consistency, not
scientific validity or modern adversarial authenticity.

## Adding a dataset

1. Add/reuse a species entry with scientific name and stable species ID.
2. Add source records with explicit review status.
3. Add a distinct dataset ID; record stage/sex/specimen, scope, coverage,
   modality, version, source IDs, license, and access status.
4. For automatic fetching, add `selected_assets` with an exact filename and
   public HTTPS URL. Record upstream size and checksum when available.
   Do not manufacture a checksum from an unrelated ETag.
5. Keep counts source-qualified. Clearly mark incomplete proofreading,
   missing boundaries, or functional-only resources.
6. Validate the catalog and downloader tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

The tool does not normalize different file formats or validate their
scientific content. Those adapters and biological validation belong in a
later simulation/data-processing stage.
