# First fly milestone: sugar stimulation to MN9

## Goal and scope

For the later persistent habitat connection, see [live neural feeding](LIVE.md).
This page retains the independently verified original reproduction baseline.

Reproduce a bounded computational prediction from
[Shiu et al., Nature 2024](https://doi.org/10.1038/s41586-024-07763-9):
**100 Hz activation of labellar sugar-sensing neurons activates MN9 in
every stimulated trial**.

This uses the original **FlyWire 630** processed network, not the newer
783 network. It is one condition from Figure 1d and the upstream tutorial,
with an additional no-input network control. It is **not** a reproduction of
the entire paper, a simulation of a body, or new experimental validation.

- Upstream code: [philshiu/Drosophila_brain_model](https://github.com/philshiu/Drosophila_brain_model/tree/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960)
- Pinned commit: `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`
- Protocol: [experiment.json](experiment.json)
- Runner: [run_flywire_sugar.py](../../scripts/run_flywire_sugar.py)
- Dataset catalog ID: `flywire-model-630`

The paper's main text reports MN9 activation in 100% of simulations at
100 Hz sugar stimulation. It separately reports only 1/100 weight-shuffled
simulations activating MN9. This milestone checks the intact network only;
we have **not** reproduced the weight-shuffle control.

## Acquire the pinned inputs and source

Choose a writable external directory and set `FLY_DATA_DIR` to it. This
session used the user-selected mounted XFS volume. Do not commit local
storage paths or data payloads.

From the repository root:

```bash
python3 scripts/datasets.py fetch flywire-model-630 \
  --asset 2023_03_23_completeness_630_final.csv --data-dir "$FLY_DATA_DIR"
python3 scripts/datasets.py fetch flywire-model-630 \
  --asset 2023_03_23_connectivity_630_final.parquet --data-dir "$FLY_DATA_DIR"
python3 scripts/datasets.py fetch flywire-model-630 \
  --asset model.py --data-dir "$FLY_DATA_DIR"
python3 scripts/datasets.py fetch flywire-model-630 \
  --asset LICENSE --data-dir "$FLY_DATA_DIR"
```

Inputs plus source/license total **89,701,540 bytes**. Downloads are verified
using the exact size and Git blob SHA-1 from the pinned upstream tree, and
receipts include local SHA-256. Existing download bundles are not overwritten.
Git blob hashes establish consistency with the selected upstream objects;
they are not an independent guarantee of biological accuracy.

Upstream model code remains unchanged in external storage. Its MIT license
is retained; underlying FlyWire data and paper attribution still apply.

## Environment

The experiment uses **Python 3.10**, Brian 2 **2.5.1**, and a C++ compiler.
The acquisition tool and catalog tests remain standard-library-only.

```bash
uv venv --python python3.10 .venv
uv pip install --python .venv/bin/python \
  -r experiments/flywire-sugar/requirements.lock.txt
```

The [requirements](requirements.txt) pin direct scientific dependencies.
The generated [lock file](requirements.lock.txt) also pins transitive
dependencies. Use `uv pip` for the uv-created environment; it does not need
an installed `pip` module.

This is a Linux-compatible reproduction environment, not a byte-for-byte
copy of the upstream Windows Conda export. Brian 2 and core parameters match
the original model; the local dependency versions are recorded in results.
Do not promise bit-identical results across different CPUs or environments.

## Run

One-trial compatibility/smoke test:

```bash
.venv/bin/python scripts/run_flywire_sugar.py \
  --data-dir "$FLY_DATA_DIR" --run-name smoke-001 --trials 1
```

This writes `incomplete_smoke_test`, never a successful full reproduction.

Full protocol:

```bash
.venv/bin/python scripts/run_flywire_sugar.py \
  --data-dir "$FLY_DATA_DIR" --run-name baseline-001
```

Use a new run name for every invocation. Existing result directories are
rejected, not silently reused or overwritten.

## Validations and implementation

Before running, the runner rechecks each input against its pinned Git blob
and receipt. It validates:

- 127,400 unique integer neuron IDs.
- 14,687,178 aggregated connection rows.
- Both presynaptic and postsynaptic IDs match their simulation indices.
- Positive contact counts, allowed sign values, and signed-weight products.
- All 21 stimulus neurons and the MN9 readout are present.

The network contains **52,793,639 summed contacts** represented by those
aggregated edges.

We reuse upstream `create_model` and `poi`, without changing their equations,
weights, thresholds, synaptic delays, refractory handling, or stimulus
scaling. Instead of rebuilding the network in joblib workers, the runner
restores its initial state before each serial trial and sets an explicit
seed. This improves reproducibility and limits concurrency on a shared
machine. The full network remains present even though relatively few
neurons respond to this stimulus.

Protocol: 30 stimulated trials, 1 second each, 0.1 ms timestep, 100 Hz
Poisson stimulation, seeds **420–449**. The resting control uses one
1-second trial and seed 420.

Acceptance requires **MN9 spiking in all 30 stimulated trials** and
**zero total spikes in the no-input control**. The control checks the model's
resting behavior, not a real fly's spontaneous activity.

## Saved results

External result location:

```text
<FLY_DATA_DIR>/results/flywire-630-sugar-mn9/<run-name>/
  protocol.json
  status.json
  summary.json
  trials.csv
  spikes.parquet
  neuron_rates.parquet
```

Results retain spike IDs/times, trial summaries, and per-neuron rate
statistics, including neurons with observed zero spikes. Summary metadata
contains graph counts, seeds, Python/core dependency versions, protocol and
runner hashes, wall time, peak process RSS, and acceptance status.

Failures are reported explicitly and recorded in `status.json`; partial
failed runs are retained for diagnosis. Do not interpret the presence of
files as success.

## Verified first result (2026-10-10)

`baseline-001`:

| Measure | Result |
| --- | ---: |
| MN9 activated trials | **30/30** |
| MN9 mean rate | **66.5667 Hz** |
| MN9 rate standard deviation across trials | **4.8627 Hz** |
| Resting-control spikes | **0** |
| Whole-run wall time | **34.4 s**, with compiled code cached |
| Peak resident memory | **4,316 MiB** |
| Saved result bundle | **1,758,066 bytes** |

A separate invocation of the original upstream `run_trial`, using seed 420,
matched **every spike's neuron ID and time** in baseline trial 0 (time
tolerance 1e-10 ms). The one-trial smoke result also matched that trial.
An independent complete run, `baseline-replay-001`, reproduced all spike
events, per-neuron rates, and non-timing trial summaries **exactly** with the
same seeds. Its acceptance checks also passed.
The first compilation is slower than a cached run.

The initial environment occupies approximately **399 MiB**, and the external
data/results footprint was approximately **89 MiB** before replay.

## Next scientific milestone

Reproduce a wider frequency-response curve and a connectivity-specific
intervention, such as the published weight-shuffling or selected-neuron
silencing experiment. Then compare against archived paper outputs and
evaluate uncertainty before attempting body/environment coupling.

Do not infer realistic feeding behavior from MN9 activity alone.
