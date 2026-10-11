# neural-brains project instructions

## Purpose and priorities

- Maintain a growing, cross-species catalog of brain and nervous-system
  mapping datasets as research and new releases become available.
- Use the collection to complete reproducible programming and simulation
  projects, not to mirror every raw imaging archive.
- The user selected the fruit fly as the active simulation track. Keep
  C. elegans as a smaller complementary project, not the next task by default. Worm
  networks are smaller, but smaller anatomy does not establish complete
  physiological knowledge or guarantee faithful behavior.
- The user also selected biomechanical walking with interactive 3D terrain
  and perturbations. Reuse validated body frameworks; do not substitute a
  scripted avatar or label CPG/reflex locomotion connectome-driven.
- Keep other species in the collection even when only partial maps, draft
  data, or restricted access exist. Do not imply whole-brain completeness.

## Starting a session

- Read [README](../README.md) and inspect the working tree before changing
  existing work. Use [the catalog](../research/sources.json) as the inventory
  of record; derive current species/dataset counts rather than hardcoding them.
- Consult [the acquisition guide](../docs/dataset-catalog.md) and
  [storage planning](../docs/storage-planning.md) before selecting downloads.
  Use [the research dossier](../docs/connectomics-research.md) for scientific
  context, modeling assumptions, and known source discrepancies.
- Do not automatically download, install simulation environments, or run a
  network-wide release sweep just because a new session starts.

## Catalog and research conventions

- Prefer primary papers, official dataset portals, and provider metadata.
  Distinguish reviewed documentation/abstracts from inspected data and
  experimentally reproduced results.
- Keep species, specimen, sex, developmental stage, anatomical coverage,
  modality, proofreading status, version, and access terms explicit.
- Preserve historical releases when adding new ones. Do not silently replace
  a reproducible snapshot with mutable latest data.
- Record exact asset URLs, byte sizes, upstream checksums, license provenance,
  and review date when verified. Unknown values must remain unknown.
- Retain conflicting counts with source/scope attribution. Synaptic contacts,
  aggregated edges, cells, neurons, and functional ROIs are not interchangeable.

## Acquisition and simulations

- Large data, generated results, and credentials stay outside Git.
  Downloads require an explicitly selected asset, approved external storage,
  and a suitable byte limit. Never bypass checksum or license uncertainty
  silently; use the documented explicit opt-in where appropriate.
- Reuse [the acquisition tool](../scripts/datasets.py); preserve receipts and
  raw exports separately from derived simulation inputs.
- Start with a bounded biological question and an observable acceptance test.
  Use existing published models where possible, but pin their code/data.
- Keep measured topology separate from assumed dynamics, weight/sign rules,
  sensory encoding, motor decoding, and body mechanics. A moving avatar is
  not evidence of a faithful animal simulation.
- Preserve identifier precision, coordinate units, and snapshot consistency.
  Keep chemical synapses, electrical gap junctions, and end-organ connections
  distinct. Prefer sparse connectivity; benchmark memory/runtime before scaling.

## Validation and continuity

- Catalog/acquisition tooling is Python 3.10+ with the standard library. The
  fly experiment uses an isolated Python 3.10/Brian 2 environment and pinned
  requirements; see [the experiment guide](../experiments/flywire-sugar/README.md).
  Validate catalog
  or acquisition changes with `python3 -m unittest discover -s tests -p 'test_*.py'`.
  Offline tests do not validate remote scientific data or biological behavior.
- Update directly related documentation and source metadata when research,
  download status, or project results change.
- After a meaningful milestone, update the short state below with date,
  verified progress, blockers, and next action. Keep detailed evidence in the
  linked docs/catalog, not duplicated here. Record an external storage choice
  only when agreed; do not store credentials or private machine-specific paths.

## Current state (2026-10-10)

- 2026-10-11 documentation milestone: main README is a concise purpose/
  capabilities/conservative quick-launch overview; original technical
  detail and current architecture are in readme-2.md. Professional nine-page
  docs/neural-brains-whitepaper.pdf has architecture, measured causal/physical
  results, negative results, reproducibility and primary references. Rebuild
  via scripts/build_project_whitepaper.py (optional ReportLab). Paper explicitly
  distinguishes actual neural initiation, assumed assisted transitions and
  learned policies; latest targeted landing tests are not broad release proof.
- 2026-10-11: user prioritized natural/brain-linked landing after reporting
  endlessflight, finger-onlytakeoff and walking-boundarypause. Added explicit
  --brain-linked-landing --landing-surface-vision: actual flight DNp10 counts
  initiate assumed assisted brake/descent/wing-to-leg cycle, realcontacts,
  1s assistancefade then unassisted learned walking. NOT measured biological
  landing; reviewed DNp10 evidence supports legextension only. Surfaceinput
  bounding silhouettes->existing LC4/LPLC2 is assumed, not verified natural
  LPLC3/LPLC4 pathway. [Evidence](../docs/brain-linked-landing.md):
  scene cycle brain-surface-final-001 request1.68s,touchdown3.68s,release4.68s,
  11601stableunassistedsteps,zeroassistancepostrelease. DNsilencing prevents
  landing whileGF/flight remain; standalone seed424phase.8 passes; exact
  intact/shamqpos/qvel/action/force parity. Walkinggroundboundary15s passes,
  engineered reference not neural gait. Spontaneoustakeoff STILLmissing.
  Prior010closed; userapproved solelive011 at8840 with these options.
  User reiterated SINGLEPORT: app+mainlauncher+interactiveDashboard now
  enforce DEFAULT_PORT8840; reject alternate/ephemeral ports, no fallback.
  Only read-only unit HTTPfixtures may use testports, withoutphysical/brain
  workers. Never run alternate-port app tests next to liveapp again.
  brain-surface-final-002 remained FAILED/interactively perturbed: finger
  toggles caused secondtakeoff/landinglate; logs/scope retained, not final
  controlled proof.238tests7skips. Check currentlive011/edits before restart;
  preserve all prior failures and explicit assumed-vs-neural boundaries.
- 2026-10-11: user praised flight, selected habitat width/depth -25%.
  Unified defaults now use grassland-habitat.json v3, matched grassland-feeding
  and112.5mm half-size (225mm wide), old v1/v2 scenes preserved. 70 rigid
  objects incl48grass blades,14material definitions,soil texture/daylight;
  3 actual free-body seeds/chaff with assumed mg masses/friction. Body-indexed
  wind and fly-only ground-contact counts prevent free props corrupting fly
  physics/landing measurements. Legacy non-unified backends reject v3.
  [Evidence and preserved failures](../docs/grassland-habitat.md): upright
  learned walking pushes seeds6.46/16.34mm, off-path0, exact qpos/qvel/action
  replay; minimumupright.9929. Compact flight15s passes, coupledGFlaunch8s
  passes36950post-assistance ticks/no floorcontacts/boundarypause. Original
  tighter-turn20cm/s compact launch failed; deployed reference15cm/s with
  original3rad/s turn bound. Tall flowers moved beside route, multiheight
  obstacle rays avoid wing clipping; lowgrass excluded before memory budget.
  Failed trials retained; do not relabel scripted/learned motion biological.
  231tests7skips +EGLrenderer checks. Old008closed_by_user; user approved
  start and then daylight save/restart. Sole live interactive-app-010 at8840
  uses binaryvision,neural-leg-extension,flight-avoidance,newgrassland.
  Latest fixed edits empty preserved; userpause/friction/camera settings
  restored via loggedcontrols, check currentstate before changing. Movable
  object poses recorded in old summaries/logs; explicitrestart newepisode,
  not seamlessstate transfer. Physicalfeeding/flexibleplants/landing/neural
  flight remain incomplete; browser world/eyes/contactlabels verified.
- 2026-10-11: user reported boundary freeze/no organic flight and explicitly
  chose engineered avoidance usability fix. Added --flight-avoidance:
  predictive bounded turn references through learned wing policy, privileged
  arena/body state and ray-detected geometry memory, no neural-flight claim.
  [Evidence and retained failures](../docs/flight-avoidance.md): final 20 s
  reversed-heading/phase .35 flight passes (16.27 mm clearance, zero floor
  contacts, no external steering force/pose reset), diagonal phase .8 and
  repeated raised-obstacle trial pass; exact obstacle qpos/qvel/action replay.
  Same-body GF launch/5 s flight with saved scene passes; failed late-turn,
  obstacle-contact and reference-drift bundles preserved. Legacy straight
  control still fails at .726 s. Failed landing experiments remain disabled.
  223 tests reported / 7 skips. Latest physical-approach browser run included
  user scene edits and is labeled INTERACTIVE, not pristine controlled data.
  User removed all placed objects; preserve that latest empty list rather
  than restoring old three spheres. Sole ongoing interactive-app-008 at8840
  now uses binary vision + --neural-leg-extension + --flight-avoidance.
  No graded vision, failed landing or automatic test stimulus in live app.
  Check current app/user edits before restart; emergency boundary stop remains
  for failures, walking boundaries/organic flight/landing still unfinished.
- User authorized stopping the old 8840 app and requested ONE live instance.
  Old 005 saved/stopped; three edited spheres preserved. Added approved
  opt-in --graded-vision continuous sphere size/velocity input to exact
  LC4/LPLC2 populations; strict rate IPC, geometry histories, source/edit/
  visibility reset and pause handling. Binary baseline remains unchanged.
  [Evidence and live deployment limits](../docs/graded-visual-feedback.md):
  graded-feedback-002 passes 44 trials / 100 checks with source hashes
  unchanged, seeds 420/423, sensory replay/cut and source/DN/motor controls.
  Tiny motor-dependent rate changes did NOT change spikes/physics; do not
  call this feedback stabilization or calibrated physiology. 001 retained
  as non-frozen integration run with explicit provenance audit.
  Actual 100-Hz binary/graded parity: 58,750 spikes; 104 LC4 / 210 LPLC2
  exact input identities. 219 tests / 7 skips; explicit legacy activity
  suite 10/10 separately, graded parity and compiled geometry tests pass.
  Graded live 006 caused actual GF launch from saved spheres and safety stop
  at 0.75 s, DNp10 silent; limitation retained. User selected binary vision
  + reduced neural leg extension for live use. 006 saved/stopped; sole
  interactive-app-007 at 8840 now uses --neural-leg-extension WITHOUT graded
  vision or engineered landing, with preserved objects/control settings.
  User then enabled finger; actual looming/GF flight later safety-paused.
  Check current state before changes; no automatic resets or second app.
- Implemented user-approved opt-in DNp10 physical leg extension via an
  explicitly assumed reduced bilateral VNC/activation-to-position-actuator
  surrogate, not reconstructed VNC/muscles or touchdown. See
  [evidence, exact missing interfaces and reproduction](../docs/neural-leg-extension.md).
  Final dnp10-extension-004: 48 trials / 102 checks passed at brain seeds
  420/421/422, including prospective 422; sham/reset exact, visual-output
  disconnection and DN voltage-clamp silencing eliminate recruitment,
  motor-disconnected physical control passes. Earlier short-pulse/feedback
  failures 002/003 remain failed; no decoder gains fitted to rescue them.
  Same-browser --neural-leg-extension defaults OFF; incompatible with
  engineered landing. dnp10-browser-002 validates final reduced-vs-calibrated
  scope flags; prior paired browser peak tibia change 0.2457 rad.
  208 tests reported / 6 skips; actual activity/parity suite 10/10 separately.
  Original port-8840 interactive-app-005 remains untouched/safety-paused;
  preserve edits and ask before restart. Missing calibrated visual/DN
  response, real VNC/muscle physiology, leg proprioception, robust touchdown
  and walking recovery remain explicit blockers; tiny geometric feedback
  differences do not prove spike-pattern changes or stabilization.
- Continueddevelopment:takeoff+telemetry worker now exports39exact candidate
  readouts(12steering/landing,27DNg02subtypes) fromexistingcountmonitor.
  ActivityReader verifies all against sparse counts;no extra neural input,
  connections,or motor decoder. Dashboard open candidate panel,clickinspect
  labels retain ambiguousDNa04/05 and historicalDNp07/10fields;counts follow
  live/historicalview. Real1s visual probe58750networkspikes,7candidatecells
  firedinclDNp07right27/DNp10left15;legacyoutputs exactvsreadoutdisabled,
  resetreplay/silentcontrolpass.191tests6skips(defaultenv),explicitactual
  activitysuite10pass. Userappinteractive-app-004 may run8840;check before
  replacing. Primary MANCmatchingtable downloadnotacquired(interstitial),
  officialEPMCsupplementAPItimedout;failedreceipts retained notusedasCSV.
  Data-backed neural steering/landing motor integration STILLunfinished.
- User reaffirmed steering/landing must be evidence-based neural,NOT engineered
  fallback. Primary landing fulltextPMC7444277 acquired+checksummed:DNp07/
  DNp10 cause state-dependent leg extension,not complete freeflight touchdown;
  octopamine gatesDNp07 differently fromDNp10. MANC fulltextPMC13384506
  wing sections reviewed:DNa04/05 candidatew-cHIN paths,putative electrical
  contacts/uncertain NT signs,not measured conductance. Verified final
  Namiki2022PMC9206711 supersedes preprint-only status. AddedsourcesS47–S51.
  Verified59,149byteCC-BY archiveZenodo20532930,MD5verified,selectedputative
  electricaltable includes5w-cHINgroups,no conductances. sensorimotor audit
  selects12allbrainmatched candidates:4landing IDs from hemibrain_type;
 8steering candidates because historicalDNa04/05aliases conflict with
  DNae004/006celltypes. Preserved ambiguity,no silent mapping. Exactincoming
  counts/partners audited externallysensorimotor-paths-001. Source receipts
  inprimary-evidence-001;documentationneural-landing-evidence.md.
 188tests5skips. NO neural motor controller changed/landing completion claim;
  calibrated VNC/neuromuscular and state/visual transfer data remain missing.
- Last interactive-app-002 had2444real network spikes/22GF/MN9silent,
  boundary interval silent,then explicitQ command closed app (no crash).
  Dashboard now records bounded episode spike totals + last nonzero sparse
  packet at/api/activity-summary;deduplicates repeated pause sequences,
  clears on reset. UI Live interval vs Inspect last firing interval with
  explicit HISTORICAL time/count label,not invented current spikes.
  Persistent boundary banner says app remains open/camera+neural inspection
  available;Resume disabled,Reset required. Preserves user priority not
  adding rule-based navigation. Actual approach1.5s300mm test still passes,
  624network spikes,last firing170ms;flying continues without continuous
  neural encoding.184tests5skips. interactive-app-003 may runat8840 with
  original plants and0edited objects;check before restart.
- User requested half flight arena and better finger responsiveness,then
  explicitly chose neural steering research rather than another rule-based
  navigation baseline. Unified app default half-size150mm(was300),width300mm;
  preserved6objects. Normal finger now20mm per WALL second,credits<=100ms
  per update,physical moves/lag/clock logged;pause/safety stop no motion.
  Prescribed --test-approach remains simulation-time and exact0.14s GF
  handoff/5300flightsteps parity passed in explicit300mm test arena.
  Browser continuous pointer debounce replaced by33ms throttle;100-event
  regression proves no postponed timer. Safety message distinguished from
  edit rejection. Live interactive-app-002 at8840 may run;check before replacing.
  Neural research primary preprints: DNg02 optomotor involvement but unilateral
  activation yields bilateral amplitude,NOT a simple steering decoder.
  audit_flight_steering.py exactDNg02 subtype labels selects27/all modelmatched;
  no stimulation/motor wiring;see docs/flight-steering-evidence.md.183tests
  reported5environment skips. No procedural/random turning added.
- User approved switching live browser to flight-capable single-body backend.
  Main --backend unified invokes .venv-flight/scripts/fly_flight_app.py at8840;
  working walking backend retained/default for comparison. Shared plants/
  materials/four saved objects,brain feeding,sparse neuron telemetry/edges,
  threaded observer,FlyBody256px rectilinear eyes and pointer are connected.
  Normal launch requires physical visible unoccluded finger expansion ->
  actual GF spikes ->0.3s assisted launch ->learned straight-reference flight.
  Not neural navigation;landing/recovery absent. Explicit300mm arena;5mm
  boundary margin freezes physical/neural time with visible safety notice,
  requires Reset (NOT braking/landing). Physical approach final bounded test
  passes initial floor contact,qpos/qvel exacthandoff,1.06s post-assistance
  flight,no floor contacts/safety stop. No-approach walks,noGF/no launch.
  Tests178reported5skips;EGL renderer4tests separatelypass. Live
  results/fly-unified/interactive-app-001 may run at8840;finger currentlyoff,
  no automatic demo stimulus. See docs/flight-browser-app.md.
- Ground observer now uses independent WorldRenderer thread with own model/
  data/OpenGL context,latest immutable snapshots,no mj_step/source-array
  races. BrowserInputs routes camera queue independently of physical
  environment queue,both bounded. Actual planted app20camera requests:
  accepted-input->encoded-frame p95 44.6ms (EXCLUDES browser display).
  Paused body/brain camera updates pass;errors propagate,shutdown joins.
  Real EGL ownership/failure tests4pass;exact gait parity separatelypasses.
 173tests reported5skips in flight default;EGL render tests run explicitly.
  User approved restart;single-app-threaded-001 at8840 may be live with
 four preserved objects. Saved camera-latency-check.json is evidence.
  CPU physical throughput and flight integration are still unresolved.
- CPU gait observation cache now enabled in walking run: caches anatomical
  indices/contact membership,NOT physical values/rates. Pinned FlyGym
  GaitObservationReader uses identical force accumulation order.
 1000tick exact observation/action parity incl reset passed;two alternating
 5000tick runs:whole gait1.816s->1.442s(1.26x throughput),observation
 .388s->.071s,exact final qpos/qvel. External gait-cache-benchmark-001.
 169tests reported,3 environment skips;actual FlyGym parity separately
 passed. User approved restart:single-app-gait-cache-001 at8840 may run,
 four edited objects preserved. This is NOT whole-app26%/real-time claim;
 GPU neural migration,threaded observer and flight integration remain open.
- First measured single-app performance pass: world image1280x960,JPEG95
  no chroma subsampling; independent world polling/publication caps30Hz,
  neural panel5Hz. Physics,brain,gait and sensory schedules unchanged.
  Bounded PhaseTimings writes performance.json once/sec incl cold-start
  vision,neural waits,world GPU render/readback and encoding. Live GPU
  usage13%,local HTTP~1ms; gait CPU loop is major remaining bottleneck.
  Retina cold Numba compile~2s is not recurring work. Live render~1.94ms,
  encode~3.26ms,coupled interval~94.7ms including warmup,NOT real-time/p95.
 168 tests reported,2 skips. User approved restart,single-app-optimized-001
  at8840 may be live,objects preserved. Flight STILL not in browser app;
  independent refresh is not threaded physics or neural GPU acceleration.
- User explicitly requested ONE browser app,not separate native world and
  dashboard. Main fly_habitat.py interactive now defaults to browser app:
  authoritative server-rendered ground-world JPEG plus eyes/neural panels
  at8840. --native-window opts back into legacy separate viewer;headless
  bounded tests unchanged. No second browser physics engine. Bounded
  session/origin-checked POST/api/input queues documented environment/camera
  events only; no W/A/S/D steering. Left orbit/right pan/wheel zoom,buttons
  pause/reset/finger/food/objects/friction/push/close. Finger projection uses
  normalized ground-image coords,no xdotool. Object-edit errors/control
  toggles visible. Render capped15publications/s but UI polls5Hz,NOT30FPS.
  Actual local Chrome verified images/layout,pause/camera,neural selection,
  mobile430px no overflow. Live direct tests verified clock pause,object
  persistence and paired reset/resume. Closing browser tab does NOT stop
  app;Save and stop/Q does. See docs/neural-dashboard.md. single-app-002
  may be live; check before replacing user session.
- User chose small planted habitat. Optional version-2 scene at
  experiments/fly-walking/planted-habitat.json adds13 static plant/flower/fruit/
  surface primitives and7 explicit visual/contact materials. V1 roundtrips
  unchanged. Shared object_definitions supplies mm FlyGym/converted cm
  FlyBody with reserved/duplicate names,bounds/material/size validation.
  Actual compiled contact geometry and leaf-ray interception pass in BOTH
  backends. Observer preserves explicit _material specularity/shininess.
  Main --feeding-config experiments/flywire-sugar/planted-feeding.json aligns
  approximate sugar exposure to fruit9,2,1mm; no spontaneous initial contact.
  Odors remain Gaussian proxies,plants rigid,friction uncalibrated; no neural
  navigation/landing claim. Main0.5s eyes+worker+dashboard bounded test passed;
  FlyBody0.2s walking scene smoke passed.162 tests reported,2 skips in flight
  environment (opt-in actual network and FlyGym-only scene test);FlyGym scene
  test separately passed. See docs/planted-habitat.md. Stable planted viewer
  session001 may be running at8840; preserve user work,check before restarting.
- User approved single-body FlyBody prototype rather than FlyGym/FlyBody
  transfer. scripts/fly_unified.py keeps legs/wings/ground contact and maps
  verified published walking/flight channels by name. Walking1s passes
  (2.025cm forward,upright0.9968,error0.0429cm); airborne0.5s150mm arena
  passes (error0.0408cm,no contacts/exits). Actual GF-triggered assisted
  walking-to-flight1.5s300mm arena passes: trigger0.32s, qpos/qvel exactly
  preserved,mass/inertia unchanged,0.8798s post-assistance flight,no exits.
  Native --view test passed and holds inspection until Q; free camera,
  P/Space pause,C tracking,source state guard. Learned policies/privileged
  references and0.3s external launch assistance remain explicit, not
  biological motor decoding. --takeoff-test uses explicit visual-population
  stimulation0.3–0.4s (NOT fitted eyes/finger). Landing trials001–003 fail;
  actuator deployment variant worsened attitude and was not adopted.
  Existing main habitat/dashboard remains unchanged; not yet wired to
  unified backend. See docs/unified-fly-prototype.md.154 tests reported,
  one opt-in real-network test skipped. Preserve failed external results.
- Normal companion dashboard now reuses http://127.0.0.1:8840/; occupied ports
  fail explicitly, no silent fallback. --dashboard-port 0 is an explicit
  ephemeral test override. Server session IDs and response headers prevent
  cross-restart data mixing and clear old selections/activity/eyes.
  Selected incoming/outgoing chemical-contact pages and partner navigation
  now use a verified external memory-mapped index of all 14,687,178 edges.
  Exact source checksum, commit and ordered IDs are bound in its receipt;
  reuse under data-root/derived/flywire-630-connections, no anatomy inferred.
  LC4/LPLC2-to-GF contact totals match prior audit (382/468 left,431/622 right).
  Signed contacts are upstream assigned proxies, NOT conductances/electrical
  junctions. Baseline/reset/silent controls passed again. 148 tests reported,
  one opt-in actual-network test skipped by default and passed explicitly.
  Initial loaded object placements now persist in each new run's objects.json.
- User selected a loopback companion browser dashboard for the firing map.
  `fly_habitat.py --neural-dashboard` serves actual eye renders above a
  schematic index map of all 127,400 neurons. It exports exact sparse
  interval counts, string IDs, episodes/sequences and source clocks.
  Baseline telemetry on/off preserves 65 MN9 / 9,840 total spikes;
  reset replay and silent control passed. Full suite: 141 tests, one
  opt-in actual-network test skipped by default; that test passed explicitly.
  Real browser picking matched index 116889 / root ID 720575940639198653 /
  18 spikes in a recorded actual interval; live eyes and responsive layout
  passed. Complete JSONL logs retain all intervals; 5 Hz UI polling explicitly
  labels gaps and retains only 40 received history entries. Map is NOT anatomy
  and still lacks region annotations; selected chemical connections are now
  inspectable as described in the newer state entry. Server is read-only loopback,
  eyes refresh by publication revision, and shutdown is bounded.
  See docs/neural-dashboard.md and docs/neuron-telemetry.md. No measured
  p95 latency, long-duration throughput or biological motor completion claim.
- Main finger input now uses spherical angular diameter and actual eye-camera
  field/occlusion gating; binary rates are still uncalibrated. Quantitative
  Ache response data/full methods were inaccessible, so no fitted physiological
  parameters are claimed. Electrical current kernel is unit/conservation
  tested but not connected without verified junction/VNC membrane parameters.
- User explicitly approved experimental hybrid physical takeoff. Separate
  `fly_takeoff.py` uses real GF spikes to initiate 0.3s of disclosed external
  force/torque assistance, then learned flight on the same FlyBody. Fixed
  1.5s test passed initial floor contact plus >0.5s unassisted wing-policy
  flight; no-approach control stayed grounded. This does NOT resolve
  physiological VNC/muscle decoding or create a unified walking/landing body.
- `fly_habitat.py --virtual-finger` adds an opt-in X11 pointer-controlled
  physical sphere (H enables) and verified LC4/LPLC2 inputs with actual GF
  counts. Binary angular expansion is an uncalibrated encoder; no physical
  takeoff or trained-flight handoff exists. Shared PoissonGroup visual input
  is not bit-identical to original per-neuron PoissonInput probes.
- Historical FlyWire annotation v1.1.0 supplies verified 630 root IDs.
  Takeoff audit found 104 LC4, 210 LPLC2, and bilateral GF/DNp01, all in the
  original model; direct chemical inputs were exported. Do not continue
  treating the brain-side ID mapping as unknown, but electrical/VNC/muscle
  decoding and validated looming response remain missing.
- Original whole-brain artificial activation probes produced GF spikes
  from LC4, LPLC2, and combined populations with silent no-input control.
  This is not a calibrated looming stimulus or physical takeoff. Next:
  validate feature encoding and response timing, not a GF-to-flight switch.
- User prioritized true neural takeoff-pathway research over engineered
  automatic walk-to-flight switching. See takeoff evidence doc: LC4/LPLC2
  looming inputs and GF timing are supported, but exact version-630 IDs,
  electrical/VNC transmission and muscular decoding remain unresolved.
  Do not script flight initiation and call it neural takeoff.
- Main habitat enables copied observer-model graphics. Physics and retinal
  models retain their original parameters; visual-only changes must not
  affect sensory/behavioral assumptions. Same-state GPU eye renders show
  small existing one-channel-level variation; exact pixel parity isn't claimed.
- Main user experience is `scripts/fly_habitat.py`: environment-only,
  automatic hybrid components, persistent until closed, no direct steering
  or controller mode selector. Keep neural feeding vs engineered
  perception/walking/recovery disclosed. Retain lower-level research
  controls for reproducibility, not as the main launcher.
  Do not claim removing UX modes makes the entire animal connectome-driven.
- First live neural integration: optional FlyWire-630 feeding worker, driven
  by geometric oral-probe/sugar-region exposure, with actual MN9 spike readout.
  See [live guide](../experiments/flywire-sugar/LIVE.md). Continuous chunks
  match the seed-420 baseline; exposure withdrawal retains residual activity.
  Worker runs in the original Brian environment, with checked brain/body
  simulated clocks and explicit paired reset. Locomotion, self-righting, and
  flight are NOT controlled by this circuit. The feeding marker is a readout,
  not physical proboscis actuation or calibrated gustatory perception.
- Walking now uses the same native integration-state guard as flight to
  protect synchronized controller/brain state. Native simulation panels and
  force edits are not supported; preserve application controls and free camera.
- Eye inset is top-right and fits the scene viewport. Retina intensity now
  influences engineered sensory-demo steering when vision is enabled; this
  is not connectomic/biologically validated visual processing.
- Optional `--self-righting` uses only joint actuators, not pose resets.
  Nominal inverted starts recovered with/without vision; 168.54-degree
  perturbed start timed out. Keep it experimental and preserve the failure,
  rather than claiming general self-righting.
- Walking camera defaults to free pan/orbit; C toggles explicit tracking.
  Optional `--vision` exposes rendered/fisheye-corrected eye views and
  ommatidial channels, not connectomic visual control. Engineered proximity
  avoidance starts earlier and considers side clearance; a 10-second test
  remained upright. Fallen-state reporting is explicit; self-righting and
  walking-to-flight transitions remain unimplemented.
- Native viewing uses `sim_viewer.py` to wait for render-thread shutdown.
  Scientific results can be saved before a graphics teardown failure;
  verify process exit separately. The first persistent walking check hit
  GLXBadContext at teardown, and a post-fix native run exited cleanly.
- Preserve the ongoing habitat while extending flight. Walking
  `--until-closed` runs until Q/window close and streams records to disk.
  Flight retains a bounded physical interval but holds its viewer afterward;
  `--exit-on-complete` opts into auto-close. A short flight diagnostic is not
  a substitute for continuous habitat behavior.
- Catalog, external-data acquisition tool, and fly experiment runner exist.
- The user chose external storage on the mounted XFS volume. Confirm the local
  `FLY_DATA_DIR` in a new session; do not commit machine-specific paths.
- Original FlyWire-630 processed inputs and unmodified model source were
  downloaded with pinned Git blob verification. Linux-side `.venv` uses
  Python 3.10 and Brian 2 2.5.1; use `uv pip`, not `.venv/bin/python -m pip`.
- A separate `.venv-biomechanics` uses Python 3.13 and pinned FlyGym/MuJoCo.
  See [walking guide](../experiments/fly-walking/README.md) for launch controls.
  Native viewing and headless rendering work; physics/controller throughput
  is currently about 0.28-0.30x real time. GPU acceleration is not enabled.
- The walking habitat now has configurable terrain/walls, sensory proxies,
  capped thorax drag, typed motor commands, and exact replay of scheduled
  keyboard perturbations. Gaussian odor/light and range rays are engineered
  approximations, not validated fly sensory physiology.
- `.venv-flight` isolates pinned FlyBody/dm-control/MuJoCo flight.
  Supplied wingbeat/reference data were checksum-verified; their GPL-3.0+
  dataset license differs from upstream Apache-2.0 code. Two aerodynamic
  wing geoms and native wing/frequency controls were tested. Published policy
  inference uses TF CPU 2.8.0 / TFP 0.16.0; newer serialization failed and
  must not be aliased or silently substituted.
- The fixed measured-reference flight benchmark passes 7/9. Phase index 22
  (seed 4, trajectory 48) loses control; trajectory 57 exceeds 45 degrees
  reference-relative error. Preserve cases/thresholds; do not inflate scores.
  A separate one-second synthetic navigation goal passes tracking checks;
  longer durations and other goals are not generally validated.
- Flight viewer physics belongs to the application. Native reset/play data
  edits are rejected to prevent Composer/policy desynchronization; native
  control panels are hidden. P/Space controls application pause, with a
  visible state/time label. Recommended goal launch starts automatically.
  Raw W/S/A/D overrides require explicit opt-in in trained mode; they are
  not navigation keys.
- Walking and flight now load the same habitat JSON. Flight `--scene`
  currently requires `straight-goal` mode and converts physical lengths/
  forces explicitly. Never regress to a plain floor when the user selects
  the habitat. Preserve dimensions and report boundary exits; the existing
  60 mm arena is too small for a full second at 200 mm/s. Proxy observations
  are logged, not wired to the published flight policy yet.
- Walking uses mm/g/s and flight uses cm/g/s. Do not directly exchange
  physical coordinates, forces, or observations without explicit conversion.
  Shared `sim_units.py` now handles conversions and exact timestep budgets.
- First full 30-trial 100 Hz sugar-to-MN9 baseline passed, with a silent
  resting control. Original upstream trial parity was checked spike-by-spike.
  Independent full seeded replay matched all scientific outputs exactly.
  This is not a full paper or whole-animal reproduction.
- Worm workbook checksum/reuse terms remain unverified. Several additional
  species require exact asset or developer-terms review.
- Next: investigate the retained flight failures and reproduce/compare newer
  controller checkpoints; calibrate sensory encoders and improve physical
  throughput. Takeoff/landing and neural/body coupling remain unimplemented.
  Preserve the neural baseline. Claim greater realism only against specified
  kinematic/physiological datasets and matched metrics, not appearance or
  unsupported comparisons with other demos.
