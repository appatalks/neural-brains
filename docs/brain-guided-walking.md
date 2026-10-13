# Brain-guided hybrid walking (2026-10-11)

**Current main-launcher default:** unified brain-guided walking/landing and
surface input now auto-enable with the [puddle habitat](puddle-habitat.md).
Explicit `--no-*` comparison flags are available. The opt-in language below
describes the initial milestone and low-level research API, not the current
main-launcher default.

`--brain-guided-walking` is an **opt-in neural-output/body interface**, not a
reconstructed VNC, physiological muscle controller or complete autonomous fly.
The conservative launcher and observation-only `--walking-readouts` are unchanged.

## What controls what

| Component | Implementation and boundary |
| --- | --- |
| Walking initiation/speed | Actual bilateral BDN2 and oDN1 spike counts determine the requested speed. |
| Ground turning | Actual DNa02 plus primary DNa11 left/right counts determine the requested turn. DNa11 has historical community alias DNa01; experimental driver correspondence is not silently assumed. |
| Walking inputs | Modeled 150 Hz BPN locomotor drive. Privileged scene/ray cues stimulate P9 and FG for turning/stopping. These are assumed encoders, not reconstructed vision, touch, internal energy or spontaneous cognition. |
| Legs | Existing published learned walking policy follows the decoded reference. Joint actuation is not reconstructed connectomic VNC control. |
| Takeoff | Existing actual GF initiation and disclosed 0.3 s assisted launch. No spontaneous-takeoff timer is added. |
| Flight | Existing learned wing policy; optional flight avoidance remains engineered, not neural flight steering. |
| Landing | Actual DNp10 initiation, with explicitly assumed braking/descent/transition and fading external assistance. |

Primary identities and causal background are in
[walking evidence](walking-neural-evidence.md). Exact IDs remain in
[the interface module](../scripts/fly_brain_walk.py); worker telemetry verifies
the counts against sparse full-network activity. There are 71 candidate readouts
in this mode: the earlier 67 plus two steering pairs. Stimulation targets 16
upstream BPN/P9/FG cells, not the eight decoded cells.

## Declared engineering interfaces

- Walking rates use a 100 ms exponential filter. Speed is
  `2*clip(min((BDN2sum-60)/80, (oDN1sum-15)/30), 0, 1)` cm/s.
- Steering rates use a 250 ms filter. Combined left-minus-right rates are
  corrected by an uncued neural baseline learned with a 200 ms filter.
  The deadband is 8 Hz, gain 0.08 and limit 2 rad/s.
- Zero requested speed gates turning off. This prevents an old learned
  baseline from becoming fictitious resting rotation after neural input ends.
- Physical acceleration limits are 10 cm/s² and 4 rad/s².
- A rolling reference integrates these commands, with 200 ms measured-position
  correction. The learned policy also uses privileged body state and future
  reference samples. No body pose or velocity is reset to follow it.
- Rays sample three headings at two heights. The current 45 mm predicted-boundary cue
  (previous25mm cue retained in historical runs),
  20 mm object cue and 4 mm emergency FG cue are engineering assumptions.
  Geometry affects neural input, not a separate direct body turn command.

These constants are not measured physiological parameters or globally optimal
values. Startup cues before uncued baseline estimation, unfamiliar objects,
arbitrary terrain, prolonged blockage and recovery need broader validation.

Brain intervals are computed ahead but **accepted only after their matching
physical interval**. Thus a just-received count packet affects the next interval,
not physical time that preceded the spikes. Pausing freezes both clocks; paired
reset clears neural filters/reference state. Walking is primed during landing
release and its reference is initialized from the measured touchdown state.

For this hybrid only, assisted descent uses angular gain/damping 2000/100
instead of legacy 800/50. Contact rollout with the legacy gains failed for the
new launch state. Force/torque caps, touchdown gates and assistance fade were
not weakened. The stronger values are disclosed external assistance, not
neural/muscle recruitment; assistance is exactly zero after release.

Fallen ground posture causes an explicit safety pause after 150 ms of contact
with upright cosine below 0.5. This is not biological death or self-righting.
Camera/neural inspection stays available; Reset is required.

## Measured results and retained failures

External evidence is under `results/brain-guided-hybrid` in the agreed data root.
The fixed five-second neural input profile tests rest, forward, left, right,
FG stopping and withdrawal. Inputs are explicit tests, not natural stimuli.

| Measurement | Seed 420 | Prospective seed 433 |
| --- | ---: | ---: |
| Forward displacement, 0.7–1.2 s | 9.776 mm | 10.149 mm |
| Left heading change, 1.7–2.2 s | +0.478 rad | +0.646 rad |
| Right heading change, 2.7–3.2 s | -0.224 rad | -0.544 rad |
| Stop displacement, 3.8–4.2 s | 0.083 mm | 0.021 mm |
| Minimum upright cosine | 0.9876 | 0.9921 |

Both profiles pass all 11 fixed physical/command checks.
`causal-002-sham` has exact interval qpos/qvel/action/force and neural count
parity with `neural-body-profile-002`. Source-output cut, decoded-cell voltage
clamp and motor disconnection each eliminate the walking reference: forward
window motion is 0.256 mm versus 9.776 mm intact. Motor disconnection preserves
the entire actual neural count stream. Metadata scope wording was corrected
during this integration cohort; it is not an all-files-frozen release benchmark.

`walk-flight-landing-cycle-004` and `cycle-heldout-433` both pass the unchanged
full-cycle gates: 4,000 unassisted-flight ticks, actual DNp10 request at 1.41 s,
stable touchdown 3.26 s, release 4.26 s, and 18,701 stable unassisted walking
ticks. Post-release displacement is 57.11 / 52.13 mm; landing assistance after
release is zero. Takeoff/landing handoffs preserve qpos/qvel and mass/inertia.
The cycle uses an explicit launch input followed by a physical looming sphere;
it does not prove natural takeoff or general surface-selected landing.

### Environment-only integration, not general stability proof

`environment-cycle-002` runs 17 s without finger input or a prescribed neural
test stimulus. Modeled BPN/scene drive evokes actual GF takeoff at 12.05 s;
surface input produces a DNp10 request at 12.43 s, touchdown 14.28 s and
assistance release 15.28 s. It subsequently walks 34.20 mm with zero landing
assistance and ends with 3,878 consecutive stable unassisted ticks.
The closest boundary clearance is 6.48 mm; the run does not safety-pause.

This is **automatic input-evoked behavior**, not validated spontaneous
physiology. Assisted launch transiently inverts the body (upright -0.928);
post-release ground posture briefly reaches 0.681. Thus it fails a uniform
ground-upright >=0.8 criterion and is not broad safe-flight/terrain proof.
The flight interval is too short for the minimum-duration benchmark.
These limitations remain open despite observed successful release/recovery.

Retained negative results:

- `neural-profile-001`: DNa02 alone did not reliably provide both turn signs.
- `neural-body-profile-001`: ungated baseline correction created resting
  rotation and a fall. The zero-speed turn gate addresses that interface bug.
- `walk-flight-landing-cycle-001`: scene cue contained a NumPy Boolean and
  failed strict JSON serialization; actual compiled-scene regression now covers it.
- `walk-flight-landing-cycle-002`: surface input evoked early landing and
  successful released walking, but only 700 flight ticks. The minimum-flight
  acceptance gate remains failed, not relabeled as a pass.
- `walk-flight-landing-cycle-003`: sufficient flight, but legacy assisted
  contact rollout fell over without stable touchdown. Hybrid-only descent
  attitude stabilization fixed the development case before seed 433 was tested.

Previous [VNC/relay failures](relay-uncertainty-test.md) remain failed and are
not rescued or replaced by this different high-level hybrid.

## Launch and reproduce

After the normal verified external-data setup:

```bash
: "${FLY_DATA_DIR:?Set FLY_DATA_DIR to your verified external data directory}"
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --brain-guided-walking --flight-avoidance \
  --neural-leg-extension --brain-linked-landing --landing-surface-vision \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/hybrid-$(date +%Y%m%d-%H%M%S)"
```

One instance, port 8840 only. Preserve the latest saved object list explicitly
with `--objects` when resuming user configuration; results are not complete
resumable brain/body checkpoints. No interactive instance is automatically
started by implementation or tests.

Bounded profile: use `scripts/fly_flight_app.py` in `.venv-flight-py311` with
`--brain-guided-walking --seconds 5.3 --test-walking-control --controlled-test`.
Causal variants add `--research-walking-control` with `sham`, `source-cut`,
`output-silence` or `motor-disconnect`.

Full-cycle reproduction adds `--seconds 8 --flight-avoidance
--neural-leg-extension --brain-linked-landing --test-stimulus
--test-brain-landing --controlled-test`, without surface vision for this
separate-cue benchmark. Each run requires explicit `--data-dir` and a new
external `--output-dir`. Research controls require bounded duration and never
become ordinary browser controls.
