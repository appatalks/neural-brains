# neural-brains | Technical reference

Implementation, data provenance, experimental evidence and reproducibility.
For the project overview and quick launch, see [README](README.md).
For the research narrative, see the [project whitepaper](docs/neural-brains-whitepaper.pdf).

## Current architecture and scope

The active track is a connectome-informed fruit-fly simulation in one browser
app. The catalog also retains datasets for six other species; cross-species
coverage does not mean whole-brain completeness.

| Component | Current implementation | Scientific boundary |
| --- | --- | --- |
| Brain | Persistent FlyWire630 model: 127,400 neurons / 14,687,178 aggregated chemical connections | Topology is version-matched; homogeneous dynamics and weight/sign rules are model assumptions |
| Sensory input | Approximate sugar contact and visible angular expansion; optional graded/surface experiments | Not calibrated receptors, compound-eye encoding or natural landing pathways |
| Takeoff initiation | Actual identified GF spikes | Physical lift uses explicit 0.3 s assistance |
| Walking / wings | Published learned FlyBody policies on one articulated body | Not connectome-generated muscle recruitment |
| Flight direction | Engineered predictive reference with physical geometry feedback | Privileged geometry, not neural navigation |
| Landing research | Actual DNp10 initiation with an explicitly assumed assisted motor transition | Bounded demonstrations; biological calibration and broad robustness remain open |
| Environment | 225 mm grassland; 70 fixed objects, 14 materials, three movable seeds/chaff | Rigid stylized vegetation, assumed masses/friction; not physical food consumption |
| Observatory | Authoritative world, eyes, exact sparse neural counts and connection inspection | Neural map is schematic, not anatomical |
| C. elegans microscope view | Cook 2019 chemical/electrical cell graph, Kato2015 calcium playback, and opt-in anterior-touch topology relay | Explicit assumed relay gains/decoder; no spike inference, calibrated synapse/body physiology, physical muscles, or cohort-matched sex/stage assertion |

The ongoing objective is to close **sensory -> brain -> descending/VNC ->
muscle -> physics -> sensory feedback**. The current hybrid contains genuine
neural causation in bounded behaviors, not a complete biological motor loop.
Spontaneous takeoff, neural directional flight, calibrated VNC/muscles,
proprioception and robust natural landing remain incomplete.

### Prepared environment

Use Linux and the separately pinned environments; do not combine them:

- `.venv`: Python 3.10 / Brian2 brain model.
- `.venv-biomechanics`: walking framework and main browser launcher.
- `.venv-flight-py311`: Python 3.11, FlyBody, MuJoCo and published TensorFlow policies.
- `.venv-worm`: Python 3.13 worm data conversion with pinned PyArrow/openpyxl.

Follow the existing [neural setup](experiments/flywire-sugar/README.md),
[walking setup](experiments/fly-walking/README.md) and
[flight setup](experiments/fly-flight/README.md) for installation and pinned
requirements. Acquire only selected, verified assets using
[the dataset acquisition guide](docs/dataset-catalog.md).
Large datasets and all generated trial bundles stay outside Git.

### Launch the current puddle habitat

From the repository root, with all environments and verified assets prepared:

```bash
export FLY_DATA_DIR="/path/to/neural-brains-data"
: "${FLY_DATA_DIR:?Set FLY_DATA_DIR to your existing external data directory}"
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --flight-avoidance --neural-leg-extension \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/session-$(date +%Y%m%d-%H%M%S)"
```

Replace the placeholder with your existing external data directory in the same
terminal used to launch. Activating a virtual environment does not set
`FLY_DATA_DIR`. An empty value resolves the input path to the repository and is
rejected; inputs must be outside Git, and each output directory must be new.

Open **http://127.0.0.1:8840/**. This is the only allowed interactive-app port;
alternate and ephemeral ports are rejected. Save/stop an existing instance
before launching another. There is no alternate-port fallback.
This starts an explicit new episode; it is not a seamless state transfer.

The main command now auto-enables neural-guided walking, actual-DNp10 assisted
landing and the assumed surface encoder. For the older comparison add
`--no-brain-guided-walking --no-brain-linked-landing`.
Read [the current puddle/fullscreen guide](docs/puddle-habitat.md) and
[landing evidence and limitations](docs/brain-linked-landing.md).
The faster, body-readiness-gated descent revision is still undergoing
robustness validation; earlier passing trials do not validate every subsequent
parameter change.

### C. elegans microscope view

The complementary worm microscope overlays the pinned adult hermaphrodite
chemical/gap-junction matrices and two bounded Kato2015 calcium recordings.
The graph uses exact cell labels but a schematic layout; fluorescence is an
observation, not action potentials. Its **Activity map** switches between
recorded fluorescence and a synthetic touch-relay visualization. The manually
evoked anterior-touch pulse uses an opt-in, clearly disclosed topology-relay
surrogate to trigger bounded kinematic reversal; Kato fluorescence does not
drive that response. The header's fullscreen control expands the same app;
**Esc** exits fullscreen.

Prepare the external bundle and start the UI only when port 8840 is free:

```bash
: "${WORM_DATA_DIR:?Set WORM_DATA_DIR to the approved external data directory}"
.venv-worm/bin/python scripts/worm_data.py \
  --data-dir "$WORM_DATA_DIR" \
  --output "$WORM_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json" \
  --sex hermaphrodite \
  --recording WT_NoStim.mat=worm7 \
  --recording WT_Stim.mat=worm0
python3 scripts/worm_microscope.py \
  --model "$WORM_DATA_DIR/derived/celegans-kato-2015-two-recording-view-v1.json"
```

Open **http://127.0.0.1:8840/**. Read the
[worm connectivity/activity evidence and limits](docs/worm-microscope.md)
before interpreting the view. The workbook's upstream checksum and license
are unknown; it is approved for local-only evaluation and must not be
redistributed.

Optional `--walking-readouts` adds primary-verified walking/stopping neurons
to the observation panel after acquiring the selected primary ID supplement.
It does not control gait or add neural stimulation. See the
[walking pathway tests and remaining motor interface](docs/walking-neural-evidence.md).

Default `--brain-guided-walking` enables the
[tested brain-guided hybrid](docs/brain-guided-walking.md): genuine BDN2/oDN1
speed and DNa02/DNa11 turn requests, modeled upstream drive/cues and learned
legs. Combined with brain-linked landing it resumes neural-guided walking after
assistance release. Flight steering remains engineered/learned and physiological
internal-energy control is absent. This does not enable the failed VNC relay.

Use `--objects /previous/session/objects.json` to restore fixed editor
placements. Loose-object trajectories remain in the run telemetry/summary;
an explicit new episode initializes those bodies from the scene.

| Control | Action |
| --- | --- |
| Left drag / right drag / wheel | Orbit / pan / zoom observer camera |
| H | Enable or disable the physical finger |
| T / F / B | Sugar exposure / friction / external physical push |
| 1 / 2 / 3 | Place cube / place sphere / remove last fixed object |
| P / R / Q | Pause / explicit episode reset / save and stop |
| C | Camera following |

Camera controls do not steer the fly. Ground/wings use learned policies;
environment interventions are logged, not natural neural behavior.
Repeated pushes, edits or resets during a controlled experiment invalidate
untouched-trial claims even if the run looks successful.
`--controlled-test` is an explicit bounded research-input lock; it is not
enabled in normal interactive sessions.

### Validation layers

1. **Software contracts:** schema, units, IDs, strict input/rate interfaces,
   single-port behavior, pause/reset and bounded telemetry.
2. **Neural reproduction:** original sugar/MN9 parity, sparse count
   conservation, source disconnection, sham, silencing and no-input controls.
3. **Embodied causality:** stimulus, actual spikes, actuator effects,
   contact/kinematics and physical replay.
4. **Release claims:** preserve failed runs; separate a passing bounded
   experiment from biological calibration and broad robustness.

Most recent recorded repository suite: 240 tests reported, seven opt-in/
environment skips. An offline suite is not evidence of biological accuracy;
actual-network and physical results below are separate acceptance layers.
Experimental counts and outcomes are dated snapshots, not release guarantees.

### Whitepaper source

The [PDF whitepaper](docs/neural-brains-whitepaper.pdf) is generated from
[build_project_whitepaper.py](scripts/build_project_whitepaper.py). On a Python
environment with the optional ReportLab package available:

```bash
python3 scripts/build_project_whitepaper.py
```

This documentation builder does not start a simulation, download datasets or
change an active app. The paper is an editorial development snapshot, not a
peer-reviewed publication or claim of a complete biological fly.

## Documentation and evidence index

- [Neural fly roadmap and agent-team plan](docs/neural-fly-roadmap.md): independent work assignments, neural-map UI, embodiment, graphics and optimization gates.
- [Success checklist](docs/neural-fly-checklist.md): evidence-based milestones and release criteria.
- [Live neural observatory](docs/neural-dashboard.md): actual eyes above an interactive schematic map of exact per-neuron interval firing.
- [Small planted habitat](docs/planted-habitat.md): shared physical plants, fruit, varied contact materials, lighting and explicitly approximate odor/food inputs.
- [Compact grassland and loose objects](docs/grassland-habitat.md): 225 mm habitat, grass/soil/fruit materials, contact-driven movable seeds, physical controls and preserved flight behavior.
- [Biological fidelity progress](docs/biological-fidelity-progress.md): corrected optical inputs, tested electrical-current kernel, and explicit missing physiological data.
- [Neural takeoff evidence](docs/neural-takeoff-evidence.md): supported escape pathway, exact-data gaps, and steps before claiming brain-driven flight.
- [Observer graphics](docs/observer-graphics.md): improved rendering isolated from physics and fly sensory images.
- [Virtual finger and live GF response](docs/virtual-finger.md): physical pointer object and explicit approximate approach-to-neuron integration; no motor takeoff.
- [Experimental physical takeoff](docs/hybrid-physical-takeoff.md): actual GF initiation, explicitly assisted lift, and continued learned flight on one physical body.
- [Single-body walking and flight prototype](docs/unified-fly-prototype.md): verified motor-channel mapping and continuous walking-to-flight handoff; landing remains a retained failure.
- [Flight-capable browser app](docs/flight-browser-app.md): explicit unified backend with physical-approach/GF initiation, assisted flight and boundary safety stop; not neural navigation.
- [Flight steering evidence](docs/flight-steering-evidence.md): primary DNg02 findings, historical subtype identity audit, and limits before motor decoding.
- [Neural landing evidence](docs/neural-landing-evidence.md): verified DNp07/DNp10 identities and causal leg-extension findings; remaining physiology and touchdown requirements.
- [Brain-linked reduced landing cycle](docs/brain-linked-landing.md): actual DNp10 initiation, assumed assisted transition, stable contact/released walking and silencing controls; not calibrated biological landing.
- [Reduced neural leg extension](docs/neural-leg-extension.md): actual DNp10-to-physical-actuator increment, explicit VNC/activation assumptions, causal controls and preserved failed assays; not complete landing.
- [Continuous spherical sensory feedback](docs/graded-visual-feedback.md): graded physical-geometry input, actual-network and motor feedback controls, preserved binary comparison and explicit physiological limits.
- [Predictive flight avoidance](docs/flight-avoidance.md): tested engineered turns through learned wing control, preventing routine flight-boundary freezes in bounded trials; not organic neural flight or landing.
- [Visual-path causal controls](docs/visual-causality.md): paired chemical-output disconnection, sham, reset and no-input experiments on the actual network.
- [Technical research dossier](docs/connectomics-research.md): review of the five starting articles, primary-source checks, dataset access, modeling assumptions, resource estimates, and recommended first experiments.
- [Machine-readable source catalog](research/sources.json): dated sources, review status, dataset versions, selected download metadata, and unresolved questions.
- [Dataset catalog and acquisition guide](docs/dataset-catalog.md): species coverage, access status, and reproducible downloads outside Git.
- [Storage planning](docs/storage-planning.md): verified input sizes, project working-space budgets, and raw-archive scale.
- [Copilot project instructions](.github/copilot-instructions.md): project priorities, scientific/data conventions, and a short state snapshot for future sessions.
- [First FlyWire experiment](experiments/flywire-sugar/README.md): pinned environment, acquisition commands, protocol, and measured sugar-to-MN9 reproduction results.
- [Live neural feeding integration](experiments/flywire-sugar/LIVE.md): actual persistent FlyWire spikes driven by geometric taste exposure, with a separate MN9 readout.
- [Interactive biomechanical walking](experiments/fly-walking/README.md): native 3D viewer, terrain/force controls, and current performance limitations.
- [Trained aerodynamic flight](experiments/fly-flight/README.md): published controller, navigation goals, safe viewer playback, robustness benchmark, and known failures.

Reviewed on **2026-10-11**. The catalog currently covers **seven species and
eleven dataset entries**: nematode worm, fruit fly, mouse, human, tunicate,
marine annelid worm, and zebrafish. Some entries are downloadable; others
require portal access or further asset/terms review. Partial brain volumes
and draft reconstructions are labeled explicitly.

The original FlyWire-630 processed model inputs and source have been acquired
in user-approved external storage. A Brian 2 baseline ran the full
127,400-neuron network: MN9 activated in **30/30** sugar-stimulated trials
and the resting control was silent. This is a bounded computational
reproduction, not a full animal simulation.

The acquisition tool uses Python 3.10+ and the standard library only.
Simulation dependencies are isolated in a Git-ignored Linux environment.
An independent NeuroMechFly/MuJoCo walking sandbox now provides live 3D
interaction. It uses an upstream CPG/reflex controller, **not FlyWire neural
control**, and currently advances at about 0.28-0.30x wall-clock real time.
Configurable habitats now supply walls, terrain, sensory proxies, wind
forcing, and replayable interventions. The separate flight backend now uses
a published trained controller: **7/9 measured-reference benchmark cases
pass**, while two robustness failures are retained. A one-second explicit
navigation-goal test passes local tracking checks. **Brain-driven flight,
general flight robustness, and real-time physical throughput remain unresolved.**

### Historical baseline context

The following paragraphs preserve earlier baseline scope and reproduction
instructions. They are not a description of the current unified default.

Walking and flight share [the legacy habitat configuration](experiments/fly-walking/habitat.json).
Pass `--scene experiments/fly-walking/habitat.json` to flight's `straight-goal`
mode to retain terrain, walls, lights, fields, and unit-correct wind forcing.
The original arena is only 60 mm wide; fast flight goals can leave it, which
is explicitly reported rather than silently resizing the scene. This is
shared environment data. The current unified backend now has one physical
walking/flying body; fully neural motor control remains incomplete.

The first live integration now connects an approximate sugar-exposure region
to the actual FlyWire spiking network and MN9 feeding-circuit readout. This
does **not** replace rule-based walking or learned flight, and does not yet
actuate a physical proboscis. The overlay/logs keep these controller scopes
separate.

```bash
python3 scripts/datasets.py list
python3 scripts/datasets.py list --species caenorhabditis-elegans
python3 scripts/datasets.py plan flywire-female-brain-783
```

Fetches require an exact asset and an explicit directory outside this
repository. See the [acquisition guide](docs/dataset-catalog.md) before
downloading large files or assets with unverified licenses/checksums.

## Legacy launch and baseline experiments

### Ongoing interactive habitat

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --neural-dashboard \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/autonomous-session-001"
```

Set `FLY_DATA_DIR` to the selected external data directory. This preserves
the working habitat and keeps it running until Q/window close, with streamed
observations. The primary experience is now **environment-only autonomous
hybrid behavior**, with no steering or controller-selection modes.
The interactive launcher now defaults to **one browser app** containing the
ground world, eye views, environment controls and interactive neuron map:
normally **http://127.0.0.1:8840/**, reused across
restarts rather than opening a new port. Selected-neuron incoming/outgoing
chemical contacts can now be inspected. The map is explicitly schematic,
not anatomical.
Left drag orbits the world, right drag pans, and the wheel zooms. The app
provides pause/reset, physical finger and scene-object controls. Use
`--native-window` only for the legacy separate native viewer.
Actual FlyWire spikes drive the feeding readout; movement/perception rules
and recovery remain explicitly engineered. Editing the environment is not
the same as fully biological, connectome-generated behavior.

T toggles sugar, O terrain, F friction, and B an external force. P pauses,
R explicitly restarts the experiment, C changes camera tracking, and Q
saves/closes. W/S/A/D/X/N do not steer or switch modes in the main habitat.
The lower-level scripts preserve manual/sensory controls for reproducible
research comparisons, not the primary user interface.

In the historical lower-level baseline, flight is an additional backend, not a replacement for this
session. Bounded flight viewers now remain open after their physical interval
for inspection; use `--exit-on-complete` only for auto-closing tests.
Free-camera panning is the default; C toggles fly tracking. Optional rendered
eye views now feed an engineered bilateral-intensity steering rule, not
FlyWire circuitry. The top-right inset shows actual eye input.
Experimental leg-only self-righting is opt-in: nominal inverted recovery
passed but a perturbed pose failed. No hidden pose resets are used, and
that legacy walking entry point does not integrate flight. The current
unified browser backend is described at the top of this reference.

Continue the user-selected fly track: improve biomechanical/sensory fidelity,
performance, and measured walking/flight control, preserving the verified
FlyWire neural baseline separately. Then evaluate the MaleCNS
brain-plus-ventral-nerve-cord dataset for a sensory-to-motor simulation.
Use MICrONS as a separate structure/function benchmark, not as a complete
mouse brain. Continue expanding the catalog as research and data appear.

For future experiments, reserve 50-100 GB of external working space rather
than mirroring raw imaging. The [storage guide](docs/storage-planning.md)
separates measured asset sizes from planning allocations. External storage
was selected for this experiment; no broader disk budget is implied.
Current measurements
and the chosen fly protocol are in the [experiment guide](experiments/flywire-sugar/README.md).

Connectivity constrains a model; it does not supply all the dynamics needed
to recreate an animal. Dataset identity, version, filtering, model assumptions,
and validation must remain explicit.

## Data and licensing

Prefer versioned connection tables and selected circuit queries over raw
electron microscopy imagery. Do not commit large datasets or access tokens.
External data and software retain their own licenses; see the dossier and
catalog before reuse or redistribution. No project-wide license has been
selected yet.

## Validation

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests validate catalog/acquisition behavior, environment configurations,
sensory/motor commands, schedules, and bounded archive extraction using small
offline fixtures. Real-physics measurements and replay checks are documented
separately in the experiment guides; offline tests alone do not establish
biological accuracy.
