# Neural fly simulation: implementation and agent-team plan

**Baseline date:** 2026-10-10  
**Companion:** [success checklist](neural-fly-checklist.md)  
**Goal:** progressively replace engineered behavior with experimentally
supported connectome-informed control, while preserving a usable autonomous,
environment-only habitat.

This is a plan, not a claim that every behavior is determined by the available
connectome. "Most realistic" requires matched experimental data and explicit
comparisons, not a visually impressive demonstration.

## 1. Preserve the working baseline

Current deliverables:

- [Mode-free habitat](../scripts/fly_habitat.py) with environment interventions,
  persistent viewing, free camera, top-right eyes, and external logs.
- [Persistent FlyWire worker](../scripts/fly_brain_worker.py): 127,400 neurons
  and 14,687,178 aggregated edges from version 630.
- [Live feeding integration](../experiments/flywire-sugar/LIVE.md): geometric
  taste exposure gates actual spikes; MN9 remains a readout, not biomechanics.
- Engineered visual/proximity/odor steering and experimental leg recovery.
- [Published flight controller](../experiments/fly-flight/README.md):
  7/9 fixed reference cases pass; two failures are retained.
- 94 tests passed before this planning task. Real data/physics checks are
  separate evidence from unit tests.

The worker now optionally exports exact sparse per-neuron interval counts,
with [baseline/reset/control parity evidence](neuron-telemetry.md).
It still does not export exact event timestamps or morphology. The original
count-only contract remains available when telemetry is disabled.

Keep the original reproduction, environment, seeds, and benchmark cases
available. Never remove a failure, introduce hidden pose resets, or silently
replace a failed neural worker with rules.

## 2. First delivery: visible, accountable neural computation

### A. Neural telemetry contract

Define and test a backward-compatible versioned worker/client contract
before UI or model changes depend on it:

- Snapshot/specimen, opaque neuron IDs, contiguous simulation indices,
  sequence number, episode, interval start/end, and clock units.
- Sparse **per-neuron spike-count deltas** for each interval. Invariant:
  sum of deltas equals that interval's total network count; MN9 agrees with
  its existing readout.
- Keep no-input intervals valid and explicitly empty. Reset must clear
  accumulators and start a new episode; reject stale or out-of-order packets.
- Use string IDs across JSON/JavaScript to preserve 64-bit precision.
- Bounded subscriptions for detailed spike times and membrane state, if
  needed; don't accumulate unbounded full-brain histories.
- Explicit backpressure, disconnection, overflow, and error reporting.
  Rendering may coalesce frames, but scientific event/count logs must
  disclose any losses. Start with counts; do not fake individual event times.

Validate against the original seed-420 output: 65 MN9 and 9,840 total spikes
over the one-second stimulus, including chunked execution and reset.

### B. Synoptic interactive neuron map below the eyes

Layout:

```text
Main 3D habitat                              Right-side panels
                                            +-----------------------+
                                            | First-person L/R eyes |
                                            +-----------------------+
                                            | Neural activity map   |
                                            | selection / legend    |
                                            +-----------------------+
```

Required behavior:

- Neurons illuminate from **actual telemetry**, not animation timers or
  hand-authored activity. Label the time window: spike counts/rate,
  exact selected events, and membrane potential are different quantities.
- Pan/orbit/zoom the neural view independently of the habitat camera.
  Click to select a neuron, display ID/type/region when known, and inspect
  incoming/outgoing connections and a bounded activity history.
- Highlight sensory inputs and MN9; filter region, cell class, active
  neurons, or circuit. Provide a visible legend, scale, episode and clock.
- Display **schematic connectivity layout** first if aligned coordinates
  are unavailable. Never present generated graph positions as anatomical
  locations.
- Use verified skeletons/soma coordinates for anatomical 3D later.
  Version-783 morphology cannot be joined directly to version-630 root IDs.
  Require explicit correspondence and report unmatched neurons, or migrate
  the model as a separate validated experiment.
- Do not draw all 14.7 million edges by default. Use selected-neuron/circuit
  edges, aggregation, spatial/visual level of detail, and bounded GPU buffers.
- Selecting a neuron is observational by default. Optogenetic interventions,
  if introduced, must be explicit research actions with full logs, not a
  hidden user mode or undocumented behavioral manipulation.

Choose native viewer panels versus a browser/dashboard only after a small
prototype proves picking, resize handling, input ownership, and linked
clocks. Do not maintain two unsynchronized simulations to render the UI.

## 3. Neural control and physical embodiment

### Feeding first

Trace supported gustatory inputs to MN9 and its motor target. Gather receptor
responses, anatomical articulation, muscle targets, and measured extension
kinematics. Establish an explicit encoder and spike-to-muscle model.
Test food present/absent, withdrawal, readout-neuron silencing, and sham
controls. Keep the current mouth marker until real physical decoding is
implemented; no arbitrary "MN9 rate -> extension angle" biological claim.

### Walking and perception

Identify sensory populations and descending/VNC circuits before mapping
their activity to gait commands. The female version-630 brain does not
provide an intact brain/VNC/muscle system. Evaluate MaleCNS for anatomy
coverage while preserving specimen/sex/version boundaries.

Prioritize one bounded behavior (for example steering) before replacing
every controller. Distinguish:

1. Environment physics and sensory measurements.
2. Receptor encoding and its uncertainty.
3. Connectome network dynamics.
4. Descending/VNC processing.
5. Neuromuscular decoding and body mechanics.

Current retinal intensity steering is not biological visual processing.
Use measured optics, temporal responses, and circuit-specific encoders when
evidence supports them. Fit/calibrate on one data split and test on held-out
stimuli; never reuse the test set to tune the controller.

### Recovery, flight, and transitions

Retain recovery's failed perturbed starts and flight's failed phase/reference.
Benchmark multiple distinct phases, orientations, terrain/friction conditions,
and perturbations. Self-righting must use actuators/contact physics and
sustained post-recovery gait, not a momentary upright pose.

Flight policy currently consumes privileged future-reference signals.
Use it as a motor baseline, not a reconstructed fly brain. Remove privileged
inputs only after a supported sensory/navigation controller exists.
One shared scene description does not establish one shared body or safe
takeoff/landing. Choose a unified biomechanical model or a physically
conservative state-transfer contract before implementing transitions.

## 4. Graphics without changing scientific meaning

Available hardware checked: RTX 5070 Ti, about 16 GiB VRAM. RAM was previously
measured at 123 GiB. System disk remains about 91% used; keep large assets,
recordings, caches, and results on approved external storage.

Stage graphics work:

- Better lighting, material/texture quality, shadows and readable overlays.
- Asset license/provenance review before optional higher-resolution meshes.
- Independent UI rendering clocks and dynamic resolution for eye/neural
  panels; scientific time remains authoritative.
- Scene editor for terrain, food/light sources and forcing, with serialized
  reproducible configurations and interventions.
- Separate collision geometry from visual meshes. Image-quality improvements
  must not silently change mass, inertia, friction, body contacts, or optics.

Render 30 FPS as a provisional first target, 60 FPS as a stretch target on
this machine. These are proposed acceptance criteria, not measured results.
Noisy/waiting displays must show progress, actual simulated rate, and staleness.

## 5. Optimization gates

Measure before replacing runtimes:

- Per-step physics, controller, sensory rendering, worker simulation,
  IPC serialization, scientific logging, and dashboard rendering.
- End-to-end simulated seconds/wall second, p50/p95 update latency,
  peak RSS/VRAM, bytes logged per simulated minute, and startup time.
- Run headless and interactive profiles with identical inputs.

Start with allocations, sparse telemetry, unnecessary repeated rendering,
IPC format, and batched/compiled controllers. Consider GPU physics or a
new neural backend only after profiling and a compatibility spike.
Older MuJoCo/TF flight and current FlyGym/Brian environments are intentionally
isolated; don't upgrade the verified neural baseline to satisfy graphics.

Proposed targets:

- Responsive camera/environment UI: p95 input-to-visible response <=100 ms
  even while physics waits.
- Map p95 telemetry-to-visible delay <=100 ms after data arrival.
- Full coupled computation >=1 simulated second/wall second is a separate,
  demanding gate; frame rate alone does not satisfy it.
- No accumulating worker backlog or unbounded histories over a 30-minute
  wall-clock session.

Compare optimized/reference implementations at equal timesteps, seeds and
inputs. Require exact parity where operation ordering is preserved; for
GPU/reordered floating point, specify justified tolerances before evaluation,
compare distributions and intervention outcomes, and label divergence.
Do not increase timestep or simplify neural topology just to pass a speed
threshold without recording and validating that model change.

## 6. Agent team: bounded independent work

This task prepares the team; it does **not** launch background implementation
agents or modify the running user habitat.

Start with three independent contributors:

| Contributor | Bounded objective | Owned deliverable | Stop condition |
| --- | --- | --- | --- |
| Neural/biology agent | Verify feeding decoder evidence and identify supported next sensory/descending circuits | Cited evidence matrix, exact IDs/version, required data and uncertainty | Return verified mapping or explicit evidence gap; no guessed motor decoding |
| Telemetry/visualization agent | Prototype actual-count neuron telemetry and panel beneath the eyes | Versioned schema, worker/client tests, map prototype | Demonstrate count invariants, selection, reset/clock behavior; schematic layout labeled |
| Performance/graphics agent | Profile a fixed baseline and prototype one measured rendering/compute improvement | Profile, before/after timings, graphics/picking capability assessment | Meet parity tests or report divergence; no global dependency upgrades |

The coordinating agent retains application lifecycle, shared scene, UI
ownership, and final integration. Physical decoder implementation follows
the biology agent's evidence; it is not parallelized ahead of that dependency.
Flight/recovery is a later independent batch after the initial handoff,
not another contributor changing the same integration files simultaneously.

Rules:

- Agree on interfaces and acceptance tests first; telemetry agent defines
  its contract before the dashboard or optimizations consume it.
- Separate worktrees/branches where available; use session artifacts for
  isolated research. Assign exact files before edits and avoid concurrent
  edits to the shared habitat/worker/client.
- No agent downloads large datasets, changes the live session, installs
  conflicting dependencies, trains a policy, or alters benchmarks without
  coordinator approval and a bounded resource budget.
- No code/data/credentials sent to third-party research services.
  Public literature searches use public scientific topics only.
- Each handoff reports changed files, evidence, tests, measurable outcomes,
  compatibility deviations, failures and outstanding assumptions.
- Integrate one coherent change at a time; run targeted tests and the
  actual coupled benchmark before marking checklist items complete.

## 7. Recommended execution order

1. Freeze benchmark/protocol and define telemetry contract.
2. Launch the three bounded independent assignments above.
3. Deliver the actual-firing map beneath the eyes without altering behavior.
4. Implement evidence-supported physical feeding and its causal controls.
5. Introduce one supported neural locomotion/perception pathway.
6. Address failed recovery/flight cases and physically consistent transitions.
7. Scale graphics/performance only behind fidelity and reproducibility gates.

Completion should be measured per behavior, not as a single "true fly"
checkbox. If evidence is insufficient, record the limitation and continue
with an explicitly identified approximation rather than inventing biology.
