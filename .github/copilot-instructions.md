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

- 2026-10-13: Dependabot remediation pins flight Python 3.11 / TensorFlow CPU
  2.18.1, Keras 3.15.0 and protobuf 5.29.6; the secure runtime no longer
  depends on TFP. Sugar pins PyArrow 14.0.1 and setuptools 83.0.0.
  `FLY_DATA_DIR` is set locally to the existing external data root. The
  verified legacy flight/walking policies were converted to external float32
  TFLite mean-action artifacts; 32 synthetic cases per policy pass clipped
  action parity (max errors 7.64e-7/8.71e-5, 1e-4 limit). One-second
  converted-policy flight and walking checks pass; full robustness remains
  unclaimed. The old `.venv-flight` is untouched and used only for trusted
  one-time offline conversion, not normal runtime.

- Multi-fly milestone: user explicitly chose INDEPENDENTbrain+body and1–3 slider,
  Apply startsnew episode/preserveshabitat+placedobjects; chosefinalstart1fly.
  AddedrealsharedMuJoCo world with1..3 namespacedFlyBodyentities,195disjoint
  actuatorchannels for3, ownphysobservations, statelesspolicyweightsreused but
  separatedecoder/wingbeat/GF/landing state and127400-neuronworker perFly,
  seeds420/421/422. [Evidence/scope](../docs/multiple-flies.md):
  actual3body/brain1.5s completes, network15759/15626/375906spikes, upright
  minima.9922/.9912/.9935, mass/inertiaunchanged; explicitsharedcrosscontacts
  unitpass. Actual1->3->2->1 live lifecycle passesunique sessions, closesold
  workers, preservesplacements, Fly2eye/neuralhistory/summarydomain and
  pairedreset. Not broadmultiflight/landing/socialvision/realtimeproof.
  Allflygeoms hiddeneyes; nosocialbrainpathway. Count1legacyresearch path
  retained, multi rejectsunsupportedartificial/gradedresearchflags explicitly.
  User priorcompactapp closednormally; latestsaved sphere30.07,-57.84mm
  mustpreserveonupdatedsingle-flysliderlaunch. Onlyone8840server; slider
  rebuildsphysics+brains, notseamlessinsertion or3mirroredavatars.

- Fullscreen/compact milestone: user askededge-to-edge ground with organized
  eye/neural views, approved restart, then explicitly chose HALF FLOOR AREA
  (not halfwidth/depth). Main scene now immutablecompact variant159.099mm wide/
  depth, XY placements/puddle radius x1/sqrt2; body/object sizes/heights/mass
  unchanged, matched foodconfig. Saved sphere latest(42.52,-81.79mm) falls
  outsidecompactbounds; userapproved scaledplacement(30.07,-57.84mm),
  original retained. Prioractualwalkingboundarypause7.78s retained; assumed
  neural boundarycue25->45mm, no directbodyturn or disabledsafetyguard.
  [Evidence](../docs/puddle-habitat.md): compactnormal10s completes,
  minclearance22.16mm/groundupright.919; compact3s flightpasses11950ticks,
  nofloorcontacts,minclearance12.07mm, learnedflightreference10.6066cm/s.
  Fullscreen covercrop with correctpointermapping; righteye/mapfixed docks,
  optionalscrollinspector, truthfulcompact/HISTORICAL counts, auto-fitwhile
  userzoompreserved. Realbrowserbounds pass1024x576/720x480/344x624.
 312tests9skips. No unlimitednavigation/biologyclaim; emergencystopremains.
  Priorpausedlive closed cleanlybyQ withuserapproval. Newrestart must preserve
  scaled latestsphere, one8840 only; check actuallive status before edits.

- 2026-10-11 user approved auto-enabled hybrid + fullscreen/overlays + central
  puddle/leaf habitat and experimental fluid forces, then commit/push.
  Main defaults unified/BGwalking/DNp10landing/surfacevision, explicit --no-*
  comparisons; research run() defaults retained. New immutable v4 puddle scene,
  78static/4loose objects,16materials,4matched taste regions; historicalv3 kept.
  Nativefullscreen/eye-overlay toggle and deterministic coordinate tests pass.
  [Guide/retained failures](../docs/puddle-habitat.md): island-start001..004
  fell; user explicitly approved dry-soil spawn(-45,-65,1.278mm) forcommit
  rather than holding push. Actualdryrigid6s minupright.99153; correctedfluid4s
  actualleaf equilibrium.20682mm,zeroverticalspeed,.02000mm3displacement
  balances.02mg weight. Fluid opt-in --fluid-physics, bounded buoyancy/drag,
  implicit force integration, noCFD/waves/tension/wetting/swimming/receptors.
  Firstexplicitforce equilibrium failed; firstappfluid loose-body forces
  accumulated because onlyfly force cleared: fixedwhole-array per-tick clear,
  failures retained. 310tests9skips; no live app left. Water/island traversal,
  launch/field stability and calibrated cognition remain open. Latestfixed
  editorobjectsEMPTY; preserve userstate before laterlaunch/restart.

- 2026-10-11 brain-guided hybrid milestone: user approved completing explicitly
  assumed high-level integration. Opt-in --brain-guided-walking now maps actual
  BDN2/oDN1 speed and DNa02 + primary DNa11 (historical DNa01) turns through
  learned legs; modeled BPN/P9/FG drive, privileged scene/reference feedback,
  not reconstructed VNC or energy physiology. 71 exact readouts. Physical
  start/left/right/stop passes11checks at420 and prospective433; exact physical/
  neural sham, source-cut/output-clamp/motor-disconnect controls pass. Genuine
  zero-input silence/reset and legacy actual network regressions27/27.
  [Evidence/negative trials](../docs/brain-guided-walking.md): coupled8s GF/
  DNp10 cycle passes420/433, request1.41,touchdown3.26,release4.26,
  18701stable unassisted walking ticks, zero landing assistance after release.
  Hybrid-only descent angular gains2000/100 address retained contact-rollout
  failure; legacy800/50 and force caps/gates unchanged. Walking/flight remain
  learned, avoidance engineered; calibrated spontaneous cognition/energy and
  neural flight steering missing. 301tests9skips. Latest fixedobjectsEMPTY;
  no interactive relaunch approved/performed. Only bounded controlled tests
  used8840 sequentially. Check current live state before any deployment.
  Environment-only17s run observed modeled-drive GF12.05/DNp10request12.43,
  touchdown14.28/release15.28,34.20mm released walking,3878stableticks.
  NOT broad stability proof: launch temporarily inverted(-.928), postrelease
  ground dipped .681, shortflight belowdurationgate. Keep these failures/limits
  explicit; next is field/launch stability, not stronger biological claims.

- 2026-10-11 externalcomparison/accountability: user askswhy missing behaviors
  ifotherssolved. Verifiedprimary Eontechnicaldoc(S67): selectedDNs=oDN1
  velocity,DNa01/02steering,grooming/MN9 intoexisting bodycontrollers,
  gainsbyhand, notfullVNC/muscles; internalstate largelymissing, visionmostly
  decorative, embodiedescape notimplementedthere. PublicEonrepo inspected
  isLIF/backendbenchmarks, fullbodyrelease notidentified. NeuroCraftprimary
  README(S68) saysscriptedbodyprograms andnorunnabledownloadsyet. FlyGM
  preprintmethods(S69) trainedencoder/neuralupdates/decoder, notourrawLIF.
  [Dossier](../docs/connectomics-research.md) distinguishes absent HERE from
  unsolvedeverywhere: our walking/steering high-levelbrain/body interface
  remains incomplete; usefulapproximate integration needn't wait for every
  physiologicalparameter. No code/data install orcontroller swap performed.
- 2026-10-11 touch/state milestone: user reports obstaclefalls/no spontaneous
  flight and selected NEURALRESEARCHONLY, no engineeredassistance. Livebody
  observedinverted(upright-.86)whileUIwalking, neuralintervalsilent, no death/
  metabolism model. LatestfixedobjectsEMPTY afteruserremoval; preserveempty,
  no reset/restart/stimulation done. [Evidence](../docs/neural-touch-state.md):
  primary adultTLA->MDN touchretreat relevant (S61abstract;fulltext403);
  four primaryMDNs exactmodel IDs/canonical sides audited,40-58ascending
  inputs each, no directly mech-labeled inputs. TLAlabel/identity unresolved,
  do NOT guess fromgenericAN/iAN-MDN.2319/2364ANs modelmatched,
  only21annotationrows named;headbristles302,eyebristles1111 modelmatched
  not leg/thoraxreceptor mappings. OA-VPM4pair matches forfeedingonly;
 152predOA labels134matched includes12non-neuronannotationrows, NEVER
  driveallOAlabels asarousal. SourcesS61-S66 distinguishproprioception,
  ascendingbehaviorstate, starvationlocomotion(hours/days),feedingOA andflight.
  audit_touch_state_paths read-only completed;288tests8skips+17focused pass.
  Next: adultTLA/NOMPC identity/driver/forceencoding thenneural-only causal
  recruitment; receptor/neuromodulation/bodyfeedback gaps explicit. Live
  interactive-landing203814 at8840 leftuntouched;check currentcontrols first.
- 2026-10-11 live enablement: user requested walking/landing and explicitly
  approved learned walking with engineered ground-boundary avoidance plus
  DNp10-initiated assumed assisted landing, NOT failedbrainwalkingrelay.
  Prior203249 saved/stopped viaQ at11.23s(exit0,nosafetystop). Sole live
  interactive-landing-20261011-203814 at8840 now additionally uses
  --brain-linked-landing --landing-surface-vision, retaining flightavoidance,
  neurallegextension,walkingreadouts and savedbox+sphere. Latest3.34swalking/
  notpaused; HTTPworld/eyes200,127400neurons67readouts; browser reused/reloaded.
  Controllerpresence is NOT landingcompletion validation. Surfaceencoder
  and brake/descentassistance assumed, realDNp10 needed; no demo inputs or
  spontaneoustakeoff timer. Keep currentusercontrols/edits, no secondapp.
- 2026-10-11 live launch: user chose interactivehabitat with existing controllers
  and neuralreadouts, not experimentaljointrelay. Sole8840 instance
  interactive-20261011-203249 uses flight-avoidance, neural-leg-extension,
  walking-readouts; saved latest135133box+sphere preserved with corrected
  collisions. Prior135133 endedworkerexiterror/no diagnosticlog; failure
  retained, causeunknown. NewHTTPworld/eyes200,127400neurons/67readouts
  verified; integratedbrowser opened. User already interacting/toggledfinger,
  latestobserved6.24s flight/notpaused/no safetynotice; leave currentcontrols
  untouched. NOT controlled validation. Full landing and failedwalkingrelay
  remain disabled; gait/flight learned/engineered scopes visible. Check live
  app/edits before restart; don't open secondapp or alternateport.
- 2026-10-11 uncertainty test: user lets test. [Evidence](../docs/relay-uncertainty-test.md):
  frozen9grid mean125/250/500 at100Hz x20/40/80ms, development420/421 with
  old420/421weaktrace regression, held-out431/432 generated only AFTER
  immutable selection. Matched seededBernoulli0.1ms externalstimulus replay,
  FGcoact/FGoutputcut exactsame events; actualbrainspikes stillcomputed.
  Both neuralcohorts22checks pass.72developmentphysicaltrials+sharedbaseline,
 4candidates pass. Fixedclosestprior rule selects250mean20ms125/spike,
  unchangedVNC/recruitment/torque/reflex/fixture.24heldouttrials25/26checks,
  OVERALLFAILED:431delta.001233rad passes,432delta.000194rad fails. Matched
  FGsuppression,disconnections,replay,bounds pass. No switch/refit using
  held-out outcomes. Old00162/66 remainsFAILED; newFGcriterion isintegrated
  activation underMATCHED input, not relabeled oldunmatchedpeakcriterion.
  Selectedlegacy420developmentdelta.001014 showslittlemargin.284tests8skips
  +focused tests pass. Defaultrelay40ms62.5 andnormalgait/app unchanged.
  Next: predeclaredoperatingmargin/newindependentseeds orphysiology;431/432
  must be considered observed, not reusedasblindvalidation after fitting.
- 2026-10-11 genuine brain-spike joint test: user said lets test. Added
  isolated export_bdn2_packets.py + assumed CountRelay + offline joint runner,
  NO normalworker/gait/app changes. [Evidence](../docs/brain-spike-joint-test.md):
  brain-packets00121trials24checks pass at420/421/prospective430:
  leftBDN2 counts64/67/71, FG44/47/48; sham/reset sparsecounts exact,
  BPN-outputcut andBDNclamp eliminate readout while BPNfires; resting silent.
  BPN150Hz50..800ms, FG150Hz300..500ms explicitEVOKED, not sensory/autonomous.
  Relay62.5modelunits/spike40ms assumed100Hz->mean250, endpoints10ms;
  no retroactive/fakeeventtimes. Matched female root720575940612364530 vs
  maleMANC10093 remains separate. brain-joint-relay00133trials62/66checks
  OVERALLFAILED:420noactuation;421delta.000813rad below.001threshold andFG
  raisespeakactivation;430delta.003600rad andFGsuppression pass.
  All33causaldelivery,15disconnect,sham/reset andphysicalbounds pass.
  No gains/thresholds fitted to rescue. SharedPoisson RNG changes BPNstream
  afterFG activation; do not claim matched-input stabilization.280tests8skips
  +focusedrelaytests pass. Next: frozen uncertainty/sensitivity experiment
  with matcheddrive controls and NEW held-out seeds before any adoption.
- 2026-10-11 positive bounded milestone: user approved own computational
  reference and explicit assumed single-joint interface. [Evidence](../docs/independent-vnc-joint.md):
  vnc_reference.py uses actual148cell MANC matrix/weight selection, float64
  explicit50/800ms boundaries, no sourceclipping. own-reference001/002 each
 33checks pass incl RK45/DOP853 and tenfoldtighter tolerance; worst allcell
  sampledifference.0000711 vs.001bound; exact reset/sham; newseeds428/429.
  test_vnc_joint.py maps model-rate body12686 to assumed recruitment60ms
  and torque/localfeedback at existingcoxa_T1_left in raised weldedbench,
  not actual female brainspikes or calibratedmuscles/proprioceptors/gait.
  Physicaljoint00524trials24checks pass: pairedneural response.0108-.0221rad,
  DNcut/MNsilence/motorcut exactnoinputphysics, sham/reset exact,
  feedbackremoval changesmotion. Fixture drift.00106cm<.01bound.
  001failed negative-roundoffinput retained; explicitaccepted[-1e-8,0)
  physicalprojection reported, rawreference preserved.002fixture failure
  .01326cm retained; onlybenchweldtimeconstant2ms->.5ms changed, NO neural/
  torque/feedbackgain tuning. Fresh429 afterfixturefix;005metadata/strict
  referenceguards exactphysics vs004.274tests8skips +isolatedVNCtests pass.
  No normalgait/app changed or newdatasets acquired. Next: genuine BDN2
  spike packet delivery through explicit assumed spike-to-VNC relay into
  this bench, then coordinatedleg; do not relabel oldGPUfailures as passes.
- 2026-10-11 reference search: inspecting previously unread run_hydra.log
  establishes archive run28965859 executed2025-09-08 on4NVIDIA L40S GPUs.
  Earlier claim of whollyunknownhardware was incomplete. Current tested source
  is dated2026-09-15; found candidate historic commit
  edb18510c375dbf27e08644f172170e065c49022 dated2025-09-07T23:28:41Z
  (S60), not proved exactexecutioncommit. Rateequation/solver/timegrid/tolerance
  conventions reviewed match; historicenv declares unversioneddiffrax and
  jax[cuda12]. ExactPython/JAX/JAXlib/Diffrax/CUDA versions stillmissing,
  publictags/releases empty. [Evidence](../docs/bdn2-vnc-reproduction.md).
  A new converged computational reference is legitimate but NOT a relabeled
  match to failed authorarchive comparisons; any missing biological parameters
  must be explicit assumed surrogates, never called measuredphysiology.
  No CUDA/legacyenv/bodycontroller changes in this search.
- 2026-10-11 continuation: user approved separate CPU .venv-vnc with pinned
  JAX0.6.2/Diffrax0.7, requirements/lock under experiments/fly-vnc; existing
  brain/body envs untouched. Corrected important reproduction bug:
  mini_circuits.npz marks maxrate>.01 OUTPUTACTIVITY, not connectivity.
  Actual HDF5W_mask rows336/422/966 retain4core+144MNs=148states.
  [Current evidence](../docs/bdn2-vnc-reproduction.md): corrected native
  projected21corecausalchecks pass but3pointwise comparisons FAIL(.114/.306/
  .220 vs.05bound); denseparent intactalsofails(.113/.249/.285).
  Finite source0..1000clipping is explicit with rawextrema/counts; NEVER
  copy sourceNaN->0 fallback. Native001 rawnegative failure retained.
  Previous activitymask runs not exactmask reproductions. Full4604parent
  intactdiagnostic first4savedparameterrows allfail averagedcoxaswing/
  stance gate; this does NOT refute paperindividualMN rhythms. Sourcearchive
  lacks exact installedversions/hardware.266offline tests8skips +53focused
  isolated tests pass. No app/body decoder changed, port8840 free.
  Nextrequires trustworthy exactexecution reference and quantitative motor/
  proprioceptive transfer, not anothergain tweak or claimed whole-fly gait.
- 2026-10-11 BDN2 VNC milestone: user approved pinned reduced matrix121160B/
  table13481B (200KBcaps), parenttable671375B(1MBcap) despite unknownrepo
  license for local-onlyevaluation; then specificZenodo pruningarchive274050687B
  (300MBcap,CC-BY4). Checksums verified, sourcesS57-S59.
  [Evidence](../docs/bdn2-vnc-reproduction.md):123cells79edges,
  68LHS55RHS despiteT1Lname, parentmedianvolume666270409. Rate-model
  topology core10093BDN2->10707E1->11751E2/13905I, not brainLIFspikes.
  Initial001/002 failures retained inclnegative numericalrates;003 completed
  28cases, all4intact motoralternation gates failed, tenfoldsolver convergence
  maxdifference.00005923. No zero/clipping fallbacks. Exactauthorparameters
  and masks336/422/966:21corecausalchecks pass,3strict archived-rate checks
  FAIL(max.266/.163/.209 vs.05bound); archive002overallFAILED.
  Onsetsolverdiscontinuity suspected, not proved or patched by omittingsamples.
  Mean/sample core rhythm != motorantagonist output; motorstance silent.
  261offline tests6skips pass. No brain/body decoder/liveapp changed.
  Next: source-matched solver/parent motorcircuits then measured proprio/
  muscle and explicit spike-to-rate transfer; no guessedgain to hide failures.
- 2026-10-11: user authorized additional bounded research/data and implementation
  after validation. S56 primaryTable3 acquired25598bytes, providerMD5 verified,
  parentCC-BY4 verified; confirms BDN2/oDN1/sixBRK and canonical sides matching
  historical annotations. Old code-workbook reversal preserved; one Type1/
  SMP461 BPN inconsistency excluded, CL210 subset12 used. [Evidence](../docs/walking-neural-evidence.md):
  walking-causality001/002 each88trials76checks pass at .05/.1ms,
  seeds420/421/422/prospective425. Sugar-causality00160trials42/44checks,
  overallFAILED: P9 seed421 FGcut/clamp do not increase17oDN1spikes.
  BPN/BDN2-specific checks pass all420/421/422/prospective426; do not hide
  P9 failure or call BPN globallyoptimal. Genuine evoked spikes, not spontaneous.
  Implemented opt-in --walking-readouts end-to-end:28additional/67total,
  no added input/edges/gait decoder. Actual visual58750 and feeding65MN9/
  9840network exact on/off parity, reset/silence pass (readout-parity002).
  001 mistaken30/69expectation failure retained. Full257tests6skips pass,
  separate actualnetwork regression pass; bounded .2s app8840 completed/
  releasedport. User app had already closed before this turn; no live restart.
  Next: measured BDN2 VNC/proprioception/muscle interface; physiological
  motor mapping/spontaneous initiation remain blocked, not solved by counting.
- 2026-10-11: user selected brain-linked walking initiation/stopping audit,
  approved only pinned 63,463-byte walking-halting ID workbook, 100 KB limit
  on existing external storage; Git blob verified, release license uncertainty
  explicitly retained. [Evidence](../docs/walking-neural-evidence.md):
  24/24 selected IDs match original model, all24 source-side labels conflict
  with historical annotations; do not silently swap sides. FG/BB exact chemical
  inputs audited; BPN_SEZ_DN2-to-BDN2 alias remains provisional, BRK identity
  not assigned from near names. Added reusable audit, sources S53-S55; full
  pinned-flight EGL suite247run5skips passes. Systempython lacksMuJoCo13errors.
  NO stimuli or motor decoder changed, live8840 untouched. Next: primary
  SupplementaryTable3 identity/laterality resolution, frozen neural-only
  coactivation/silencing/sham tests, then justified VNC/muscle interface.
  Injection is evoked, not spontaneous; learned gait is not neural gait.
- 2026-10-11: user reaffirmed evidence-based biological autonomy using real
  synaptic events, selected collision-only fix over engineered walking changes.
  Unified editor objects now use fixed mocap collision bodies; moving static
  geometry previously left stale collision bounds away from hidden slots.
  Load/place/remove/reset and observer poses wired; saved object format unchanged.
  41 focused tests pass incl actual FlyBody box/sphere contacts and solver forces
  at 62.5 mm, unchanged fly qpos/qvel on edits, visibility and threaded EGL.
  [Scope](../docs/flight-browser-app.md): fixed obstacles, not pushable props or
  neural touch. Walking/landing defaults unchanged; ground avoidance is still
  gated on brain-linked landing. Spontaneous takeoff, neural walking and
  metabolic energy routing remain absent. User-started session at 8840 was
  safety-paused when inspected and left untouched; check current edits before
  any approved restart. Next: deploy collision fix with preserved objects,
  then investigate evidence-based sensory/VNC/muscle interfaces, not fake
  spontaneous spikes or biological labels for learned/engineered control.
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
  Main --backend unified invokes .venv-flight-py311/scripts/fly_flight_app.py at8840;
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
- `.venv-flight-py311` isolates pinned FlyBody/dm-control/MuJoCo flight.
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
