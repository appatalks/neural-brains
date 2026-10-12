# Single browser simulation app

The main interactive habitat now puts the **ground world, eye views and
interactive neuron-firing map in one browser app**. The server renders the
authoritative MuJoCo physics state; browser images are not a second simulation.
On wide screens the ground world is on the left and eye/neural instruments
on the right. Narrow screens stack these panels.

**Fullscreen ground** now enters native browser fullscreen with eye/neural
overlays, individual visibility toggles and bottom controls. Escape or
**Exit fullscreen** restores the split layout. Letterbox margins are excluded
from physical pointer projection. See [the current environment and scope](puddle-habitat.md).

## Start

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --virtual-finger --neural-dashboard \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/neural-session-001"
```

Use a new external output directory for each run. The console prints
`Neuron dashboard: http://127.0.0.1:8840/`. Open that URL in a browser.
The URL and running/closed lifecycle are also saved in `dashboard.json`.
The normal address is stable across sessions. An occupied port fails explicitly;
the launcher does not silently create another view on a different port.
Interactive apps now accept only the centrally defined port 8840.
`--dashboard-port 0` and alternate ports are rejected; physical browser
experiments must run sequentially on the same port, not alongside a live app.
Only isolated read-only HTTP unit fixtures use ephemeral ports without fly or
neural-worker processes.

The eyes and neuron map are panels in this **one dashboard**. The server-rendered
ground image shows the authoritative physical habitat; a separate native window
requires explicit legacy opt-in. Older test URLs
may remain open in browser tabs, but their closed servers are not live
simulations. Close those tabs and use the stable address.

Each server has a unique session identity. The browser clears old metadata,
counts, selection and eye images when a restarted server appears at the same
address. Response session headers prevent a restart during an HTTP request
from mixing two sessions' data. While disconnected, current counts/images
are unavailable; retained history is explicitly historical.

The main launcher uses the browser app by default, including the dashboard.
`--native-window` explicitly restores the legacy separate native viewer;
`--headless --seconds N` remains a bounded noninteractive experiment.
Neither interface adds a fly behavioral mode or replaces actual spikes with
animation.

## Ground-world controls

- Left drag orbits, right drag pans, and the wheel zooms the server-side camera.
- Overview restores the camera, and Follow camera toggles fly tracking.
- Pause/resume and Reset act on the authoritative body/brain pair.
- Finger, sugar, friction, external push and terrain controls are available
  as buttons. Cube/sphere placement uses the last pointer position over the
  ground-world image; Remove deletes the latest edited object.
- Save and stop performs a clean shutdown. Closing a browser tab alone does
  not stop the server; reopen the stable URL to reconnect.
- The ground view is keyboard-focusable and accepts the existing environment
  keys; text fields and neural-map controls do not steer the fly.

Inputs are bounded, session/origin checked and queued onto the simulation
thread. Rejected/full requests and rejected object edits are visible in the
app. Only documented camera/environment inputs are accepted; direct W/A/S/D
fly steering is not introduced. Input requests are recorded in run events.

The ground image is a server-rendered 1280-by-960 JPEG from the observer copy,
quality 95 with no chroma subsampling. Publications and an independent world
polling loop are capped at 30 Hz; neural inspection retains its 5 Hz loop.
Actual new-frame rate is limited by slower coupled physics. No real-
time/30 FPS claim is made. Camera changes can render while physical time is
paused. Ground and eye image clocks are explicit and can differ.

`performance.json` reports bounded wall-time totals/means/maxima for coupled
intervals, eye processing, neural waits, observer sync, GPU render/readback,
and encoding. It is refreshed once per second, not a full event history.
The initial profiling run included Numba retina compilation; its cold-start
cost must not be mistaken for recurring vision work. In one higher-resolution
bounded run render/readback averaged about 2.1 ms and JPEG encoding 3.5 ms,
while coupled intervals averaged 123 ms including cold vision initialization.
These are workload-specific phase measurements, not p95 end-to-end latency.

GPU rendering is already active. The current gait and Brian network are
CPU-controlled; arbitrary parallel stepping would violate their causal state.
GPU neural integration still requires causal/numerical validation. Independent
observer rendering now has its own thread and ownership checks as described
below. Flight remains absent from this walking app.

The next CPU pass caches the pinned FlyGym anatomical/body/contact index
lookups in [GaitObservationReader](../scripts/fly_gait_observation.py).
It still evaluates every contact force, observation and controller tick at
the original cadence. It does not cache changing physical values, weaken
stumbling/retraction sensing, or reduce integration resolution.

Two alternating 5,000-tick comparisons in the planted scene measured:

| Measurement | Original | Cached |
| --- | ---: | ---: |
| Complete walking loop, mean | 1.816 s | 1.442 s |
| Observation extraction, mean | 0.388 s | 0.071 s |

This is **1.26x loop throughput**, not a 26% speedup of the whole app or
proof of real-time performance. Final qpos/qvel matched exactly in all
comparisons. A separate 1,000-tick test checked each observation and gait
action for exact equality, including a reset. The original extraction remains
available through the low-level `run(..., cached_gait_observation=False)`
comparison option. External evidence:
`results/flywire-live/gait-cache-benchmark-001/summary.json`.

### Independent ground-world renderer

[WorldRenderer](../scripts/fly_world_renderer.py) owns its own MuJoCo model,
data, camera and OpenGL context on a dedicated thread. The simulation thread
submits immutable integration/scene-array snapshots into a latest-only slot.
The observer thread never reads a body array while physics mutates it and
never calls `mj_step`. Obsolete display snapshots may be coalesced; complete
neural/physical scientific records are unaffected.

Camera inputs are routed directly to the observer queue, independently of
the body/brain interval. Environment/finger/object inputs still execute on
the authoritative simulation thread. Camera requests are also retained in
the existing run input log. Both queues are bounded; a full queue rejects
the request visibly rather than growing without limit. The finger projection
uses the most recently rendered camera, not an independently stepped body.

Rendering or publication errors propagate to the simulation instead of
silently leaving a frozen success-shaped image. Renderer shutdown joins its
thread before closing the dashboard and source physics.

In the actual planted app, **20 camera inputs under load measured 44.6 ms p95
from accepted input to encoded frame publication**. This excludes browser
transfer/decode/display and is not a whole-app latency or 30 FPS guarantee.
Camera changes also updated images during paused body/neural clocks.
Evidence: `results/flywire-live/single-app-threaded-001/camera-latency-check.json`.

Threaded EGL tests additionally verify:

- Frozen source state still permits new camera frames.
- Display changes do not alter source qpos/qvel.
- Contact/body snapshots coexist with actual eye rendering and neural IPC.
- Queue-full requests do not partially route a camera event.
- Render/publication failures are surfaced and the render thread terminates.

Independent display rendering does not make the gait or neural model
GPU-parallel or improve biological control. The separate, explicitly selected
[unified browser backend](flight-browser-app.md) now adds assisted physical
flight without relabeling the original walking backend.

## Interaction

- The top panel displays the two actual eye renders and their source clock.
  Eye frames update at the existing 10 Hz simulated-time cadence, independently
  of neural intervals; an older image is not labeled as a new observation.
- Drag the neural map to pan; use the wheel or zoom buttons to zoom.
  Fit/reset restores the full index layout. These controls never change the
  habitat camera or physically move the finger.
- Click a dot or search an exact decimal-string neuron ID to inspect it.
  Input, visual-input, MN9 and GF labels are shown where verified.
- Filter all neurons, neurons active in the received interval, or known
  circuit/input neurons. No unsupported region/cell-type labels are invented.
- Inspect selected-neuron incoming/outgoing chemical connections, 25 entries
  per direction/page, with total counts and previous/next buttons. Click a
  partner ID to inspect that neuron. At most the two displayed pages are drawn:
  teal incoming and amber outgoing, in schematic index space.
- Inspection shows interval counts and at most 40 received history entries.
  Counts are not exact event timestamps or membrane voltages.
- Recorded episode totals and the last nonzero firing packet are available
  even if the browser missed a brief activity interval. Inspect last firing
  interval is explicitly historical; Live interval returns to current data.
- Habitat pause/reset and neural episode/sequence clocks remain visible.
  A reset clears displayed activity/history rather than replaying an old
  interval. Unavailable/disconnected backend data is explicitly indicated.

In the main app, the browser pointer over the ground image targets the
physical finger and edited objects. It does not require X11/xdotool.
Moving over eye/neural panels does not change the finger target. Camera
changes alter the projection; disable the finger before camera manipulation
if simultaneous finger motion is unwanted. The legacy native option retains
its X11 pointer implementation.

## Scientific meaning and display policy

All 127,400 neurons are laid out by their verified simulation index on a
400-column grid. **This is a schematic index layout, not brain anatomy.**
No soma coordinates, morphology, or connectomic adjacency are inferred from
their positions. Drawn edges come from the verified chemical connection table,
not from the dot positions. Contact counts and the upstream assigned signed-
contact proxy are shown separately; neither is a measured conductance, a
physiological transfer fit, or an electrical-junction reconstruction.

The worker builds a checksum-verified, memory-mapped connection index under
`derived/flywire-630-connections` in external data storage. Its receipt binds
the exact upstream commit, source file checksum and ordered neuron identities.
It is reused across sessions instead of repeatedly exporting all 14.7 million
edges. The browser only receives bounded selected-neuron pages.

Each active dot is backed by an exact count from
[the sparse telemetry contract](neuron-telemetry.md). Unknown physiology
and the engineered walking/recovery/flight boundaries remain unchanged.
A silent interval really contains zero spikes; the UI does not animate
neurons merely to look alive.

The dashboard polls at 5 Hz wall-clock time and shows the latest completed
interval. It may skip intermediate neural intervals. Sequence gaps are
explicitly marked; history is **not** a complete spike-rate/event record.
Every completed interval is retained in the native run's
`neural-feeding.jsonl`. Client-side memory and server snapshots are bounded,
but complete scientific logs naturally grow on external storage.

## Local lifecycle

The standard-library app server binds only to `127.0.0.1`, uses no
external scripts/fonts/services, exposes only explicit API routes, and
rejects unexpected Host/origin access. Neural inspection endpoints remain
read-only; only the session-scoped input endpoint accepts mutations.
It is not a remote-access service.
The server closes with the habitat and its lifecycle manifest records that
closure. A saved URL does not remain live after the simulation exits.

## Validation

On 2026-10-10:

- Exact real-network baseline, count conservation, reset replay, and silent
  control passed: [telemetry evidence](neuron-telemetry.md).
- A real native habitat served all 127,400 exact string IDs, current neural
  intervals, and its actual RGB eye image through the local API.
- Browser selection found MN9 ID `720575940660219265` at index `127193`.
  Circuit filtering, zoom/fit, and the eyes-above-map layout worked.
- A fitted-canvas click on a recorded actual interval selected index `116889`,
  ID `720575940639198653`, with exactly 18 observed spikes. The displayed
  maximum count matched the packet's maximum of 18; its network total was
  1,078. Interval clock labels were rounded without altering source data.
- Narrow-screen layout had no horizontal overflow and the eye PNG loaded.
- The polished live dashboard loaded the actual 900-by-512 composite and
  refreshed only on new eye publications. Unavailable images do not cause
  repeated expected 503 requests.
- A bounded actual habitat with sugar withdrawal/reintroduction and reset
  preserved neural/body clocks, conserved all sparse counts, suppressed the
  absent finger stimulus, saved previews, and closed the dashboard cleanly.
  External bundle: `results/flywire-live/neuron-dashboard-reset-001`.
- The consolidated real browser inspected MN9's **229 incoming connections**,
  paged from entries 1–25 to 26–50, and followed a partner ID to the correct
  selected neuron. Filters reveal a selected partner rather than silently
  leaving it hidden; reconnecting refreshes its verified connection pages.

The connection index preserved all **14,687,178 aggregated chemical edges**.
An independent page-based inspection reproduced the existing LC4/LPLC2-to-GF
contact audit exactly:

| GF | LC4 contacts | LPLC2 contacts |
| --- | ---: | ---: |
| Left | 382 | 468 |
| Right | 431 | 622 |

External bundle: `results/flywire-live/connection-inspection-audit-001`.
Telemetry with indexing enabled still preserved the 65 MN9 / 9,840 network
baseline, reset replay and silent control.

Still outstanding: verified region filters, anatomical coordinates,
measured p95 display latency, long-duration
memory/logging benchmarks, and a unified biologically decoded animal.

### Single-app validation

The installed local Chrome loaded the live ground JPEG and eye PNG together,
verified wide-screen world/instrument layout and eyes-above-map ordering,
used the Pause button and Overview during paused physics, selected MN9's
229 incoming connections, and checked a 430-pixel layout without overflow.
Direct live commands additionally verified camera orbit/pan/zoom, both clocks
paused together, persistent object placement and paired reset/resume.
The native window is not launched in this app path.

Finger-visibility regression tests require every visibility flag to be a
native JSON boolean in both MuJoCo environments. A live finger-enabled
app check passed after correcting a NumPy boolean that previously caused
neural logging to stop; that failed session's logs remain preserved.
