# Visual pathway causal disconnection experiment

This isolated experiment tests causal propagation **inside the current
approximate FlyWire model**. It does not implement physical steering or
landing, calibrate visual responses, or change the running habitat.

## Intervention and controls

[test_visual_causality.py](../scripts/test_visual_causality.py) uses the
verified full network and existing 100 Hz LC4/LPLC2 input. Before storing the
initial network state, it zeros all recurrent chemical weights whose
presynaptic neuron belongs to the selected visual population.

This follows the original model's output-disconnection semantics.
It is **not neuronal spike silencing**: incoming synapses, membrane dynamics
and Poisson drive remain. No physical forces or actuator settings change.
The isolated worker/client option is not exposed as a normal app control.

Six predeclared cases are run with identical parameters at seeds 420 and 421:
intact, identical sham, LC4 output disconnection, LPLC2 output disconnection,
both disconnected, and no input. Both-disconnected reset replay is also tested.

Required checks:

- Intact and sham outputs match exactly at each seed.
- No-input network is silent.
- With both outputs disconnected, sources still fire, but there are no GF
  or observed steering/landing candidate spikes.
- Reset retains the altered weights and replays sparse counts exactly.
- Per-neuron counts agree with network totals and all identified readouts.

## Actual results

One-second intervals, no sugar contact:

| Seed | Case | Network spikes | Combined GF spikes |
| ---: | --- | ---: | ---: |
| 420 | Intact | 58,750 | 326 |
| 420 | Sham | 58,750 | 326 |
| 420 | LC4 outputs disconnected | 50,778 | 282 |
| 420 | LPLC2 outputs disconnected | 40,788 | 182 |
| 420 | Both outputs disconnected | 31,083 | 0 |
| 420 | No input | 0 | 0 |
| 421 | Intact | 58,956 | 329 |
| 421 | Sham | 58,956 | 329 |
| 421 | LC4 outputs disconnected | 50,860 | 279 |
| 421 | LPLC2 outputs disconnected | 40,838 | 178 |
| 421 | Both outputs disconnected | 31,154 | 0 |
| 421 | No input | 0 | 0 |

In the both-disconnected cases, every remaining spike belongs to a stimulated
source neuron. All 39 steering/landing candidate counts are zero. This
distinguishes externally driven source spikes from downstream propagation.
All predeclared checks passed, including exact reset replay.

External bundle: `results/flight-steering/visual-causality-001`.
Each case retains metadata, exact sparse response, selected target IDs,
number of affected edges and the intervention description. The protocol
stores source hashes; failing checks stop explicitly and preserve results.

## Reproduce

```bash
.venv/bin/python scripts/test_visual_causality.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flight-steering/visual-causality-002"
```

The output directory must be new and outside Git. This runs separate pinned
brain workers; it neither restarts nor mutates a running app.

## What this does not establish

The input is the current artificial binary Poisson encoder, not a fitted
retinal stimulus. Setting outgoing chemical weights to zero is not equivalent
to every biological silencing method. There is no calibrated landing
flight-state modulation, steering-muscle timing, VNC physiology or complete
neuromuscular decoder in this test.

Reduced GF firing supports chemical-path dependence in the model. It does
not establish natural flight navigation, a direct DN-count-to-turn mapping,
or successful touchdown. Those remain separate validation gates.
