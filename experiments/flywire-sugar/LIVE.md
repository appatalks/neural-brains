# First live FlyWire-to-habitat integration

## What is genuinely neural

The actual **127,400-neuron / 14,687,178-edge FlyWire-630 spiking network**
now runs alongside the habitat, in a separate Python 3.10/Brian 2 process.
At each habitat interval:

1. Sample an approximate oral probe's overlap with a configured sugar region.
2. Enable/disable the original 100 Hz Poisson input to the 21 right sugar GRNs.
3. Advance the complete network for exactly that interval of simulated time.
4. Read actual MN9 spikes and display/log the feeding-circuit activity.

The model's membrane/synaptic state and recurrent connections persist
between intervals. We do not fabricate MN9 rates or clear neural activity
when exposure is withdrawn.

**Locomotion, rendered-vision steering, and self-righting remain separately
engineered controllers.** MN9 does not drive legs, wings, or a modeled
proboscis in this first integration. The colored marker near the mouth is a
neural readout, not physical proboscis extension or food consumption.

## Explicit approximation at the input

[live-feeding.json](live-feeding.json) defines a sugar-exposure sphere and
an oral-probe offset relative to the thorax. Probe/region overlap is an
engineered taste-contact surrogate, not anatomically reconstructed labellar
contact, measured receptor dynamics, or sugar-concentration calibration.
Odor is not silently converted into taste. Foot contact is not mapped to
labellar GRNs.

The source sphere is a non-colliding visual marker. The chosen 100 Hz input
is the already validated protocol, not a concentration-to-spike-rate model.
Settings outside this protocol are rejected. The scope is **real neural
computation with an approximate encoder and explicit readout**, not a fully
physiologically accurate brain/body coupling.

## Run in the preserved habitat

For the main environment-only experience:

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/autonomous-session-001"
```

No mode choice is exposed. Vision-driven steering, proximity/odor rules,
and experimental recovery are enabled automatically as disclosed engineered
components. Feeding activity comes from the actual brain worker. Sugar
availability, terrain, friction, and external forces are user environmental
interventions. This is autonomous hybrid behavior—not fully connectomic
walking/flying behavior.

Use the existing isolated environments:

- `.venv`: Python 3.10, Brian 2 2.5.1; the neural worker.
- `.venv-biomechanics`: Python 3.13, pinned FlyGym/MuJoCo; habitat and viewer.

The original verified FlyWire-630 inputs must already exist in `FLY_DATA_DIR`.
See [the baseline acquisition instructions](README.md) for another checkout.
Every worker startup rechecks the pinned input/source hashes and receipts.
The brain loads once per habitat run. Startup may take several seconds.

For inspecting feeding independently from movement:

```bash
.venv-biomechanics/bin/python scripts/fly_walking.py \
  --until-closed --vision --self-righting \
  --scene experiments/fly-walking/habitat.json \
  --controller manual --drive 0 \
  --brain-feeding experiments/flywire-sugar/live-feeding.json \
  --brain-data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/interactive-001"
```

For the existing walking experience, use `--controller sensory-demo`
and omit `--drive 0`. It remains rule-based locomotion; MN9 does not control it.
The oral probe can leave the sugar region as the body walks, withdrawing
the neural stimulus.

Those lower-level options are retained for reproduction/testing, not
required by the primary launcher. Removing user mode selection does not
make the engineered components biological; their replacement still needs
validated neural pathways and physical motor decoding.

Controls:

- **T** enables/disables the sugar source, independent of walking.
- **P** pauses habitat and neural simulated time together.
- **R** explicitly resets the body and network together, increments the
  episode, and reseeds the neural model. This is user reset, not recovery.
- **W/S/A/D, N, C, Q** retain their habitat/controller/camera meanings.

The overlay distinguishes **Locomotion** from **LIVE FlyWire feeding** and
shows geometric exposure and interval MN9 rate. A red marker denotes at
least one actual MN9 spike in the last neural interval; gray denotes none.
Short intervals make the displayed rate noisy, so consult spike counts
and timestamps instead of treating the instantaneous rate as a smooth signal.

## Timing and error handling

Both processes use the same simulated interval (normally 16.7 ms; the final
bounded interval can be shorter). The brain has a 0.1 ms timestep and the
body also uses 0.1 ms. The habitat sends its exposure request before stepping
physics, then waits for the matching neural response. This allows CPU work
to overlap without letting simulated clocks drift.

This is live computation, **not a claim of wall-clock real time**. Neural
stepping adds time/memory; the viewer will run slower if either process is
slow. The ready response validates the complete network size and pinned
protocol. Missing workers, bad input hashes, protocol errors, mismatched
intervals, and response timeouts fail explicitly with a saved worker log;
there is no rule-based fallback for MN9.

The worker uses spike counts without accumulating every neuron's spike
history in RAM. Per-interval network/MN9 counts are streamed to disk.
Stimulation toggles the original Poisson-input objects' active state;
it does not rebuild the brain. No-input and withdrawal are distinct:
withdrawal can produce residual network spikes from persistent state.

## Outputs

In addition to the normal habitat files:

- `brain-metadata.json`: exact neuron/input/readout IDs, source revision,
  protocol, config, fingerprints, and Brian version.
- `neural-feeding.jsonl`: source/probe position, geometric exposure,
  matched brain/body interval times, episodes, actual network/MN9 counts,
  and the separate locomotion-controller label.
- `brain-worker.log`: explicit worker diagnostics and errors.
- Habitat `summary.json`: accumulated neural counts and statements that
  locomotion and physical proboscis are **not** controlled by MN9.

Generated outputs and biological data remain outside Git. The worker is
closed normally when the habitat exits, or terminated explicitly on failure.

## Validation completed

- One 1,000 ms stimulus produced **65 MN9 / 9,840 network spikes**, exactly
  matching the original seed-420 baseline.
- Ten successive 100 ms neural intervals produced the same totals as one
  1,000 ms interval: state is retained and chunking preserved the baseline.
- The reset followed by a no-input 1-second control produced zero spikes.
- A 100 ms withdrawal after stimulation produced residual spikes rather than
  an invented immediate zero.
- Habitat exposure/withdrawal/resumption and paired reset were exercised
  with [live-interventions.json](live-interventions.json). Every brain/body
  clock was checked, accounting for schedule execution at frame boundaries.
- An independent complete replay matched every exposure, spike-count,
  reset, and neural/body clock record exactly.
- The native coupled viewer exposed legacy native physics edits that could
  desynchronize the body. The shared viewer state guard now protects the
  walking habitat as well as flight; native simulation panels are hidden.
  Application reset/pause/force keys still work, and free camera remains.
  The protected native test matched headless neural responses exactly;
  its final body pose differed by only about 5e-8 mm.

These validate software/protocol integration. They do not validate the
geometric oral probe, full physiological sensory responses, muscle mechanics,
or whole-animal autonomous behavior.

Native mouse physics editing is not supported in this synchronized mode.
Use B for a logged body-force perturbation rather than the native Ctrl-drag
force tool. Camera pan/orbit/zoom are unaffected.

## Next core tasks

1. Calibrate labellar contact/concentration encoding against measured data.
2. Identify an appropriate proboscis/muscle body model and validated
   neural-to-actuator mapping; do not animate extension from a guessed scale.
3. Validate interventions and sensory-response latency in the coupled system.
4. Establish other sensory/descending-neuron pathways before replacing
   walking/flight baseline controllers with connectome-derived control.
