# Exact neuron activity telemetry

The optional `--neuron-telemetry` worker flag exports actual **per-neuron
spike-count deltas**, not simulated animation, inferred spike times, or
membrane potentials. It uses the existing counting monitor and does not add
synapses, stimuli, or a second network.

## Contract

The ready response retains protocol version 1 and adds
`neuron_activity_schema_version: 1` and the ordered `neuron_ids` list.
IDs are decimal strings to preserve 64-bit identity. An index refers only
to this exact ordered, verified FlyWire-630 snapshot. The ready metadata
includes the upstream commit and identified stimulus/readout IDs.

Each step adds:

```json
{
  "neuron_activity": {
    "schema_version": 1,
    "episode": 0,
    "sequence": 1,
    "start_ms": 0.0,
    "end_ms": 100.0,
    "indices": [12, 25],
    "counts": [2, 1],
    "network_spikes": 3
  }
}
```

The example is illustrative, not an observed dataset.

- Indices are unique, ascending, and within the verified network.
- Counts are positive integers; omitted neurons fired zero spikes.
- The sum equals the interval's existing `network_spikes` readout.
- MN9 and every configured GF readout agree with their sparse counts.
- Intervals are contiguous in neural simulated milliseconds.
- Sequence starts at 1 and increments for every completed interval.
- Reset increments the episode and returns sequence 0, an empty packet,
  and a zero neural clock. It never fabricates interval activity.
- No-input intervals are explicitly empty when the network is silent;
  withdrawal can retain genuine recurrent/residual activity.

[ActivityReader](../scripts/fly_activity.py) validates these invariants in the
client and rejects stale packets, discontinuous clocks, invalid identities
and inconsistent totals. Existing clients can omit telemetry; their response
fields and neural dynamics are unchanged.

## Logging and memory

The worker keeps one previous cumulative-count vector during each interval,
not a full-brain spike-event history. A packet contains at most one entry per
neuron. Habitat JSONL logs retain every completed interval, including sparse
activity, when the dashboard option is enabled. No packet is dropped on the
scientific logging path: the existing request/response backpressure remains.

These complete logs can grow substantially in long active sessions. Use
external storage and measure logging volume before a long-duration release.
The companion display can coalesce intervals; that is not a complete
scientific event log.

## Real-network validation (2026-10-10)

External result bundle:
`results/flywire-live/neuron-telemetry-parity-001` under the chosen data root.

The pinned actual network was run with ten 100 ms sugar-contact intervals,
seed 420, with telemetry disabled and enabled:

- **65 MN9 spikes; 9,840 network spikes**, matching the baseline.
- All pre-existing response fields matched exactly between the two runs.
- Every sparse packet conserved the interval's spike total and readouts.
- Reset and replay matched both sparse indices and counts exactly.
- Reset followed by a one-second no-input control produced no spikes and
  an empty sparse packet.

Warm one-second neural execution measured 1.870 s without telemetry and
1.928 s with telemetry in this single comparison. This excludes loading and
body/vision/rendering costs; it is **not** a coupled real-time or statistical
performance claim.

Unit tests additionally cover malformed packets, readout mismatch, stale
sequences, reset, silent intervals and string-ID preservation.

Repeat the real-network regression with explicit external paths:

```bash
FLY_ACTIVITY_DATA_DIR="$FLY_DATA_DIR" \
FLY_ACTIVITY_OUTPUT_DIR="$FLY_DATA_DIR/results/flywire-live/activity-regression-001" \
  .venv/bin/python -m unittest discover -s tests -p 'test_fly_activity.py'
```

The output directory must be new. Without these environment variables the
real-network test is explicitly skipped; the unit tests still run.

## Not provided by these counts

There are no exact within-interval event timestamps, anatomical coordinates,
region/type annotations beyond verified labels, or voltage trajectories.
A schematic map of these indices must not be described as an anatomical
brain reconstruction. Neural observation does not make engineered walking,
recovery, or assisted takeoff biologically decoded.

When takeoff input and sparse telemetry are both enabled, metadata also lists
`sensorimotor_candidates` and each step includes `sensorimotor_spikes` keyed
by the exact string root ID. These are observation-only readouts for separately
retained steering/landing candidates and DNg02 subtypes. The client requires
exact identity/count agreement with sparse activity. No candidate stimulation,
silencing or motor action is added by enabling these readouts.
See [candidate evidence and regression](flight-steering-evidence.md).
