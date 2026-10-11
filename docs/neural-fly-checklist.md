# Neural fly success checklist

**Created:** 2026-10-10  
**Plan:** [roadmap and agent assignments](neural-fly-roadmap.md)

Checked means supported by existing evidence; unchecked means proposed or
not yet verified. Attach run/reference links and date before changing status.
Unit-test count alone is not evidence of scientific accuracy.

## Existing baseline

- [x] Preserved environment-only persistent habitat; no manual mode selector
  in [the main launcher](../scripts/fly_habitat.py).
- [x] Actual persistent FlyWire network and original seed-420 count parity:
  [live feeding evidence](../experiments/flywire-sugar/LIVE.md).
- [x] Paired neural/body reset and chunked clock checks.
- [x] Source verification, external data storage, and visible component labels.
- [x] Working rendered eyes, free camera, and top-right eye inset.
- [x] Flight benchmark retains failures rather than claiming universal stability:
  [flight evidence](../experiments/fly-flight/README.md).
- [ ] Stable biological locomotion, self-righting, and flight driven by the
  connectome. Current engineered/learned controllers do not satisfy this.

## Gate 1: neural telemetry and map

- [x] Contract includes exact snapshot, string neuron IDs, episodes,
  sequence numbers, simulated interval boundaries, units and sparse deltas.
- [x] Per-neuron deltas sum exactly to existing total spikes; MN9 agrees.
- [x] One-second stimulus and chunked execution preserve 65 MN9 / 9,840 total
  spikes for seed 420; silent control and paired reset remain valid.
  Evidence: [exact neuron telemetry](neuron-telemetry.md), including the
  retained real-network parity/reset/control bundle.
- [x] Map sits **under the eyes**; both resize without overlapping controls.
- [x] Neurons illuminate from actual count/event data with a visible time-window
  and color-scale legend; no artificial event timestamps.
- [x] Picking identifies the correct neuron and shows bounded activity history.
- [ ] Selected incoming/outgoing edges and region/circuit filters work.
  Incoming/outgoing pages, partner navigation and known-circuit filters are
  implemented against the verified connection table; region filters remain
  outstanding. See [connection audit and dashboard](neural-dashboard.md).
- [x] Anatomical coordinates are version-matched; otherwise schematic layout
  is prominently labeled and unmatched IDs are counted.
- [x] Pausing/restarting doesn't replay stale firing; disconnected/stale data
  is visible and never replaced with fake activity.
- [ ] Detailed subscriptions, logs, and GPU geometry use bounded memory.
  Current [dashboard](neural-dashboard.md) has bounded snapshots/history;
  detailed subscriptions and long-duration logging benchmarks remain open.
- [ ] p95 telemetry-arrival-to-visible latency <=100 ms under a documented
  workload; packet loss/aggregation policy is explicit.

## Gate 2: environment -> brain -> physical feeding

- [ ] Exact receptor and MN9 target anatomy verified from primary sources.
- [ ] Sensory contact geometry and concentration/rate encoder calibrated or
  explicitly marked approximate, with reproducible parameters.
- [ ] Supported physical proboscis/muscle model selected and versioned.
- [ ] Neural-to-actuator relationship justified; readout marker is not counted
  as physical feeding.
- [ ] Extension/retraction amplitude, latency, and trajectories compared with
  held-out empirical measurements using predeclared tolerances.
- [ ] Food present/absent and withdrawal controls pass.
- [ ] Appropriate neural silencing changes predicted physical response;
  sham manipulation does not; causal tests are logged.
- [ ] No direct environmental rule bypasses the network for the behavior
  labeled neural; no invented immediate zero after withdrawal.

## Gate 3: neural perception and movement

- [x] Opt-in continuous spherical geometry-to-population-rate interface and
  reduced DNp10 chain pass 44 physical trials / 100 checks at seeds 420/423,
  with frozen source hashes and sensory replay/cut controls:
  [continuous sensory feedback evidence](graded-visual-feedback.md).
  Small motor-dependent rate changes did not change actual spikes or physics;
  neural feedback stabilization and biological calibration remain unchecked.
  Over-responsive live GF takeoff is retained, and graded vision is not enabled
  in the user-selected live baseline.
- [x] Explicitly reduced DNp10-to-physical-leg actuator comparison passes
  model causal/kinematic tests, including prospective seed 422: 48 trials,
  102 checks. Same-browser opt-in integration verified; see
  [reduced neural leg extension](neural-leg-extension.md).
  This does not check off calibrated VNC/muscle physiology, natural landing,
  empirical timing/pose matching or feedback stabilization below.
- [ ] Sensory populations, downstream pathways and VNC/muscle boundary identified.
- [ ] Specimen/sex/version differences handled; no unverified 630/783/MaleCNS
  ID or circuit merging.
- [ ] At least one bounded perceptual/locomotor behavior passes held-out
  activity, timing and kinematic tests.
- [ ] Connectomic intervention changes that behavior; disconnected/shuffled
  controls distinguish neural causation from decoder rules.
- [ ] Engineered visual-intensity steering is replaced or explicitly retained
  as a comparison, not relabeled biological vision.
- [ ] Supported muscle/effectors and uncertainty are documented.
- [ ] Unknown physiological dynamics remain visible assumptions.

## Gate 4: robust embodiment

- [x] Actual-DNp10 initiated reduced assisted landing reaches stable contact
  and upright walking after assistance removal in bounded physical tests.
  Scene-driven full cycle and DN-silencing control pass; held-out neural
  seed/wing phase and exact sham physical parity pass. See
  [brain-linked landing evidence](brain-linked-landing.md).
  Braking/descent assistance and learned motor policies remain engineering
  assumptions; natural visual/VNC/muscle calibration is not checked off.
- [x] Compact 225 mm grassland includes tested physical loose-object contact:
  upright learned walking displaces two seeds, off-path controls remain still
  and full physical replay matches. Smaller-arena flight and same-body neural
  launch comparison pass bounded tests; see
  [grassland evidence](grassland-habitat.md).
  This does not establish neurally directed manipulation, flexible foliage,
  physical feeding or stable landing.
- [x] Explicit engineered flight-avoidance comparison completes bounded
  20 s physical flight, distinct wing phases and repeated raised-obstacle
  avoidance with exact replay; same-browser GF handoff tested.
  [Flight avoidance evidence](flight-avoidance.md) retains precursor failures
  and the straight-flight boundary failure. This does not check off organic
  neural navigation, arbitrary perturbation recovery or stable landing below.
- [ ] Recovery tested over distinct initial rolls, headings, substrate friction,
  contact states and perturbations, with failure cases preserved.
- [ ] Recovery uses actuator/contact physics only and maintains upright gait
  for the predeclared post-recovery interval.
- [ ] Both existing failed flight cases pass original thresholds or remain
  explicit unresolved limitations; cases are not excluded.
- [ ] Flight tests cover genuinely distinct wing phases, not just seed numbers.
- [ ] Navigation succeeds within configured habitat without hidden resizing.
- [ ] Shared physical body or conservative transfer contract handles position,
  velocity, orientation, mass/inertia and controller state.
  [Single-body prototype](unified-fly-prototype.md) now preserves qpos/qvel
  and mass/inertia across walking-to-flight handoff. Landing and full habitat
  integration are not yet validated, so this gate remains open.
- [ ] Takeoff/landing/walking transitions preserve physics and do not teleport.
- [ ] Privileged flight-reference inputs removed or clearly disclosed.
- [ ] Long-duration and disturbance performance measured, not extrapolated
  from a 50 ms or one-second demonstration.

## Gate 5: graphics and performance

- [ ] Profiling separates physics, neural simulation, IPC, vision, logging,
  rendering, startup and interactive input costs.
- [ ] 30 FPS display target met with p95 UI response <=100 ms on the measured
  machine; 60 FPS is a separately reported stretch goal.
- [ ] Coupled physics/brain >=1x real-time throughput demonstrated at unchanged
  validated settings, or current slower rate disclosed.
- [ ] Graphics changes do not alter collision geometry, mass/inertia, contacts,
  friction or calibrated sensory images without validation.
- [ ] High-resolution assets have verified licenses/provenance and fit VRAM.
- [ ] CPU/GPU implementation passes predeclared numerical/behavioral parity
  checks; deviations are reported rather than hidden.
- [ ] Thirty-minute wall-clock session has bounded memory/queue growth,
  measured logging rate, clean shutdown and no dropped scientific data
  without an explicit policy.
- [ ] Camera movement, layout resizing, neural picking and environment editing
  work without desynchronizing body, neural or viewer states.

## Agent/integration release gates

- [ ] Three bounded work assignments accepted with exact file ownership and
  dependency/resource budgets.
- [ ] Telemetry contract accepted before consumer implementations.
- [ ] Each contributor supplies evidence, tests, failures, metrics and assumptions.
- [ ] Changes integrated without clobbering live work or another agent's edits.
- [ ] Existing baseline regressions and actual coupled run verified.
- [ ] Environment interventions/replays, hashes, seeds and status files valid.
- [ ] Documentation and future-session context reflect verified results.
- [ ] User-facing interface remains environment-only; research controls are
  explicit, separate and logged.

## Definition of a defensible release

Every advertised behavior has a traceable chain:

**source data -> encoder assumptions -> neural computation -> decoder
assumptions -> physical actuation -> measured outcome -> causal validation.**

Release notes list which gates passed, what remains engineered, what failed,
and the exact benchmark scope. Do not claim full biological equivalence or
superiority over all other demos without matched evidence.
