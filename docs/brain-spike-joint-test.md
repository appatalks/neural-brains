# Genuine brain spike packets to the isolated joint bench

**Date:** 2026-10-11. **Result:** brain packet controls passed24/24;
coupled relay/joint test **FAILED:62/66checks**.
One prospective seed produced the required paired movement, two did not.
The assumed relay gains and thresholds were not changed to rescue the result.

The subsequent [frozen uncertainty and matched-input test](relay-uncertainty-test.md)
resolves the stimulation-stream ambiguity, but its development-selected
candidate still fails one of26new held-out checks. Neither experiment is
enabled in normal gait or reclassified as validated walking.

This tests the next stage after the
[independent VNC/joint milestone](independent-vnc-joint.md). It is an
offline, evoked test, not autonomous walking or a reconstructed whole fly.

## Tested path and explicit assumptions

```text
explicit BPN Poisson stimulation
 -> original female FlyWire630 chemical LIF network
 -> genuine leftBDN2 spike-count packets
 -> assumed boundary-delivered exponential current relay
 -> separately matched male MANC BDN2/core/motor rate circuit
 -> previously fixed recruitment/local feedback/torque proxy
 -> one real FlyBody joint on the raised external fixture
```

The female brain root is `720575940612364530`; the separately matched male
MANC BDN2 body is `10093`. These are distinct namespaces and specimens, joined
by an explicitly assumed type-level transfer, not shared identity or grafted
connections. The motor output remains MANC body`12686`.

[bdn2_relay.py](../scripts/bdn2_relay.py) uses a40ms current decay and
62.5model-current units per delivered spike. This normalization maps100Hz
to a steady mean250model units. It is **not measured conductance, membrane
current or a calibrated brain-to-VNC transmission law**.

Counts are available at the end of each10ms interval. The VNC integrates
that preceding interval before receiving its packet; the packet can affect
only later time. No within-interval spike timestamps are fabricated.
Stale, gapped, wrong-episode, invalid-count or invalid-clock packets fail
explicitly. Sparse counts are checked against the original neuron-ID ordering.

The VNC continues to use the validated148-cell topology and saved336 rate
parameters, without tuning them to these brain traces. Recruitment, joint
torque/local feedback, mechanical fixture and physical bounds remain those
of the prior joint probe.

The physical feedback stays in the local torque proxy. It does not feed
sensory spikes back into the brain or VNC. The brain packets are recorded first
and replayed offline.

## Actual neural packet generation

[export_bdn2_packets.py](../scripts/export_bdn2_packets.py) loads the original
127,400-neuron,14,687,178-edge Brian2 model with verified source inputs and
primary walking identities. It adds only explicit research Poisson drivers
and causal interventions in this isolated network instance.
The normal worker and habitat launcher are not changed.

Protocol:

- Brain seeds420,421 and prospective430.
- One-second trials,100contiguous10ms packets.
- BPN12-cell input at150Hz from50ms to800ms.
- FG2-cell coactivation at150Hz from300ms to500ms in its named case.
- No sugar or looming input.
- Pinned-model Poisson targets use zero refractory period as in the original
  activation helper; other cells retain their model rules.
- Source cut zeros measured BPN recurrent output weights while preserving
  source spiking.
- BDN2 silencing clamps both exact cells' voltage/synaptic state before each
  threshold evaluation; sham applies identity updates.

The21trials include intact, sham, no-input, BPN-output cut, BDN2 silence,
FG coactivation and fresh reset replay. **24/24 predeclared checks passed.**

| Brain seed | LeftBDN2 spikes, intact | LeftBDN2 spikes, FG coactivation | Intact / FG spikes during300-500ms |
| --- | ---: | ---: | ---: |
| 420 | 64 | 44 | 17 / 1 |
| 421 | 67 | 47 | 17 / 0 |
| 430 | 71 | 48 | 18 / 1 |

Sham/reset sparse network counts match exactly. No-input is silent.
BPN output disconnection and BDN2 clamp eliminate both BDN2 readouts while
the stimulated BPN cells continue to fire.
Pre300ms FG-coactivation packets match intact packets exactly.

After FG input activates, it consumes additional random draws in the shared
Poisson stream; BPN packet counts can therefore differ slightly between
conditions. This is not a matched sensory-input replay or a full paper
reproduction. The strong observed brain-level suppression is separate from
the harder physical-transfer criteria below.

Raw packet files, full metadata, source hashes and exact-count fingerprints
are preserved in external `results/walking-paths/brain-packets-001`.

## Coupled physical test

[test_brain_joint_relay.py](../scripts/test_brain_joint_relay.py) verifies
the passed neural controls, exact file hashes and each sparse-count packet
before integration. It reuses the same FlyBody bench and physical controller,
not an independently animated joint or trained walking policy.

There are33coupled cases: seven brain conditions plus relay disconnection,
VNC motor-state silence, physical motor disconnection and feedback removal
for each of the three brain seeds.

### Passed controls

- **33/33 delivery-causality checks:** no motor rate before the first delivered
  leftBDN2 packet; first nonzero delivery is80ms in the intact cases.
- **15/15 disconnection/silencing comparisons:** BPN cut, brain BDN2 silence,
  relay cut, VNC motor silence and physical motor disconnection all restore
  exact no-input physical trajectory hashes.
- Sham/reset match both the entire VNC rate array and physical
  qpos/qvel/control/force hashes exactly.
- Local feedback removal changes the physical trajectory while adding zero
  local feedback torque. This includes passive/gravity response and is not
  proof of brain-mediated proprioceptive stabilization.
- All fixture, torque and joint bounds pass. Maximum fixture drift is
  0.001060cm; maximum actuator torque is0.0001916g*cm^2/s^2.

### Four failed scientific gates

| Brain seed | Maximum joint difference from no-input | Motor activation peak, intact / FG | Result |
| --- | ---: | ---: | --- |
| 420 | 0rad | 0 / 0 | No motor recruitment; paired-response and FG-transfer gates fail |
| 421 | 0.000813rad | 0.034858 / 0.045803 | Below0.001rad response bound; FG peak activation rises instead of falling |
| 430 | 0.003600rad | 0.095796 / 0.019778 | Paired-response and FG-transfer criteria pass |

FG reduced the brain's delivered spike count at every seed. Its downstream
motor-rate integral also decreased at421 and430, but not strictly at420
(both integrals are zero). At421, reduced total output did not imply a lower
physical activation peak.

This shows that the **assumed spike-to-current transfer does not robustly
preserve the intended motor response/suppression** across the tested inputs.
It does not imply that the real fly's BDN2 pathway fails to control walking.
The predeclared bounds remain unchanged, and the overall result remains
**FAILED**, not promoted to validation from the single successful seed.

Evidence: external `results/walking-paths/brain-joint-relay-001`.
The prospective430 outcome supports bounded feasibility of the complete
brain-spike-to-joint surrogate chain, not generalization or physiological
calibration.

## Reproduction

Already acquired external assets and existing isolated environments are used:

```bash
: "${FLY_DATA_DIR:?Set verified external storage}"
PACKETS_DIR="$FLY_DATA_DIR/results/walking-paths/packets-$(date +%Y%m%d-%H%M%S)"
.venv/bin/python scripts/export_bdn2_packets.py \
  --data-dir "$FLY_DATA_DIR" --output-dir "$PACKETS_DIR"

MUJOCO_GL=egl .venv-flight/bin/python scripts/test_brain_joint_relay.py \
  --data-dir "$FLY_DATA_DIR" --packets-dir "$PACKETS_DIR" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/relay-$(date +%Y%m%d-%H%M%S)"
```

Both outputs must be new. The second command intentionally exits
unsuccessfully if the scientific gates fail. No app, alternate port, dataset
download or default controller modification occurs.

## Next scientifically bounded question

Characterize sensitivity of the **assumed** transfer and rate dynamics to
input amplitude, decay and packet timing before choosing another relay.
Freeze candidate hypotheses/ranges and development versus new held-out
seeds before testing; retain this failed protocol unchanged.
Use controls with matched stimulation streams when attributing FG-dependent
changes. Do not increase gain solely to make these same failures disappear.

The whole-body gait, natural sensory encoders, neuromuscular calibration,
brain-body sensory feedback and spontaneous initiation remain unfinished.

Validation: **280 offline tests run, eight skipped, no failures**; focused
relay/joint tests also pass in the existing environments.
Passing tooling tests does not overturn the four failed scientific gates.
