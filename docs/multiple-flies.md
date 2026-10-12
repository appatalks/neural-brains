# Independent flies in one habitat

The **Flies** slider supports **1–3**. **Apply fly count** deliberately saves the
placed objects, closes the current brain/body workers and world server, and
starts a new physical/neural episode on the same port8840. It is not seamless
live insertion or a resumable state transfer. The scene and fixed placements
are preserved; brain/body state and ordinary controls reset.

The initial main-launcher count is one. `--fly-count 2` or `--fly-count 3`
starts directly with multiple flies. Explicit legacy walking remains single-fly.

## What is independent

- Each fly has its own127,400-neuron FlyWire-630 whole-brain worker, with seeds
  `feeding_seed + fly_index`, separate input packets, spike counts and resets.
- Each has a complete physical FlyBody with uniquely namespaced joints,
  actuators, sensors and eye cameras. All bodies live in **one** authoritative
  MuJoCo model with a shared habitat, movable props and real cross-fly contacts.
- Walking rate filters, rolling references, GF launch state, wingbeat generator,
  flight-avoidance state, DNp10 leg/landing decoder and assistance fade are
  per-fly. Neural intervals are accepted only after the matching physical ticks.
- Published motor-policy weights are reused for efficiency; the feed-forward
  policy receives each body's own observation/reference and produces that
  body's action. This does not share a brain or copy another fly's movements.
- Actuator maps are bound by the full fly namespace. Applying one actor's
  controls cannot overwrite the others' actuator channels.

There are no added inter-brain synapses or calibrated social behaviors. The
existing hybrid assumptions remain: modeled locomotor/scene input, learned
leg/wing control and explicitly assisted takeoff/landing—not complete
biological autonomy.

## Observation and controls

**Inspect Fly1/Fly2/Fly3** selects that fly's eye images, sparse neural map,
candidate counts and contact/behavior telemetry. Switching resets received
neural history/totals without inventing a new biological episode or combining
different brains' firing. Connection inspection uses their identical pinned
connectome snapshot. Follow camera tracks the inspected physical body.

Fly1 retains blue graphics; Fly2 is green and Fly3 amber. This is visual labeling,
not a biological change. All fly geoms are currently hidden from rectilinear
eye rendering, as the original self-geometry masking did; reconstructed
fly-to-fly visual/social perception is not claimed.

Food/finger toggles affect the shared environment. Each brain receives its own
oral-contact and looming/surface inputs. A push targets the inspected fly.
Pause and paired reset affect the whole shared world; one fly's genuine
boundary/fallen-state failure safety-pauses all clocks with a named-fly notice.

Multiple brains substantially increase RAM and CPU cost. This is not a realtime
performance claim. Single-fly graded/artificial research probes are explicitly
rejected in multi-fly mode, rather than silently ignored; use physical sensory
inputs and the bounded multi-body tests.

## Verified evidence

External bundles are under `results/multi-fly` in the agreed data root:

- `three-brain-body-003`:1.5s completes with three distinct whole-brain worker
  PIDs and127,400 neurons each, seeds420/421/422. Actual network totals are
  15,759 /15,626 /375,906 spikes; minimum ground upright is
  0.9922 /0.9912 /0.9935. Their trajectories differ and all bodies retain mass/
  inertia. This validates bounded independent walking, not a multi-fly
  flight/landing benchmark or unlimited interaction.
- `population-lifecycle-001`: actual1→3→2→1 requests produce distinct server
  sessions, close old workers, preserve saved placements, and return real
  packets. Fly2 observation and summary isolation pass for2/3 flies; paired
  reset advances the real brain episode and restarts the physical clock.
- Compiled-body unit tests verify195 disjoint actuator channels for three
  bodies, proper per-body observations/mass, and actual cross-fly contacts.
- Initial integration errors (`three-brain-body-001/002`) are retained; no
  missing-object-method or mass-binding failure is relabeled as a pass.

Reset and population changes are unavailable during bounded validation.
The slider never bypasses the one-server/port8840 rule.
