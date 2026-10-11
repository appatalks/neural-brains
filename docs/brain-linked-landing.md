# Brain-linked landing: actual initiation, assumed assisted motor transition

The user requested the most natural, brain-linked responses rather than a
timer-driven touchdown. This increment requires **actual verified DNp10 spikes
during flight** to initiate landing. It uses the existing full chemical FlyWire
network; no firing is fabricated and no motor timer initiates the request.

**This is not a reconstructed biological landing circuit.** DNp10's primary
causal evidence supports landing leg extension, not the entire brake/descent/
wing shutdown sequence modeled here. These motor dynamics and external
landing assistance are explicit engineering assumptions.

## What controls what

| Behavior | Actual neural contribution | Non-neural / incomplete contribution |
| --- | --- | --- |
| Walking | Neural counts observed; not the leg controller | Published learned leg policy; new engineered ground boundary reference |
| Takeoff | Actual GF spikes initiate handoff | Approximate looming input, 0.3 s external launch assistance and learned wings |
| Flight direction | Neural activity remains observational | Explicit engineered arena/obstacle reference through learned wing policy |
| Landing request | Actual flight-interval DNp10 spikes initiate request | Assumed response latch; not measured DN threshold/state dynamics |
| Braking/descent/wing-to-leg transition | Downstream of genuine request, not a new independent trigger | Assumed reference trajectory, learned policies and disclosed force/torque assistance |
| Post-landing walking | No claim of neural muscle control | Physical floor contact, learned gait; landing assistance fully removed |
| Spontaneous takeoff | **Not implemented** | No fake spontaneous activity, random flight or periodic takeoff timer |

Spontaneous takeoff and continuous neural navigation remain separate open tasks.
The optional landing response does not turn an otherwise silent model into a
biologically motivated animal or complete the sensory/VNC/muscle physiology.

## Sensory-to-neural path

[LandingSurfaceVision](../scripts/fly_looming.py) samples physical fruit, bark,
stone, wet-soil and fallen-leaf surfaces in the existing scene. It uses bounding
spheres, real eye pose, visibility/occlusion rays, consecutive angular expansion
and the existing binary LC4/LPLC2 input gate, **only during flight**.

This is an explicitly assumed surface encoder, not calibrated compound-eye
vision or the measured natural DNp10 landing pathway. The reviewed primary
landing anatomy involves LPLC3/LPLC4 relationships; the model's LC4/LPLC2
chemical propagation does not establish those identities or empirical response
curves. No new LPLC3/LPLC4-to-DNp10 anatomical correspondence is invented.

The exact female FlyWire630 DNp10 pair remains:

- Left: `720575940620153765`.
- Right: `720575940619678366`.

Their separately matched male MANC DNxl018 bodies remain in a distinct
namespace; they are not grafted into this female brain's chemical network.
DNp07 is not decoded with an invented octopamine gate. Ambiguous steering
identities remain separate.

[NeuralLanding](../scripts/fly_neural_landing.py) checks contiguous exact count
intervals through the existing verified decoder. A request records neuron IDs,
episode, sequence, delivered interval spikes and brain/body time. Counts become
available at the interval boundary; only subsequent physics responds.
Repeated/old intervals fail rather than replaying a motor trigger.

## Assumed motor sequence

After a genuine request:

1. Brake in the current physical travel direction with a smooth 0.35 s
   reduced reference, then descend over 0.75 s. The previous 0.5 s brake /
   1.3 s descent is retained in earlier result bundles, not described as the
   current timing.
2. Blend the existing flight and walking actuator channels over 0.7 s.
   The wing pattern is replaced by wing-position holding through actuator
   torque, not a physical joint reset.
3. Align to the measured yaw with an assumed upright attitude target.
4. Apply bounded external force/torque to realize the reduced transition.
   Near the ground, gravity support declines, transferring body weight to
   actual foot/floor contacts rather than continuing to suspend it.
5. Require floor contact, upright cosine >0.9 and body speed <3 cm/s for
   0.2 s after the descent window before marking stable touchdown.
6. Fade landing assistance smoothly over one second while the learned gait
   starts. Require at least 1,500 consecutive upright/contact steps
   (0.3 s) **after assistance is zero**, plus physical displacement.

These constants are declared model assumptions, not extracted VNC transmission,
measured muscle-force laws or animal timing fits. Assistance is not called
muscle actuation.

### Reducing the suspended-looking descent

The user observed the slow descent looked suspended. The updated assumptions
reduce the reference descent from 1.3 s to 0.75 s and braking from 0.5 s to
0.35 s. The neural trigger, no-reset contract and contact/release gates stay
unchanged; assistance still exists and this is not a claim of natural measured
landing physiology.

Actual-DNp10 motor trials `quicker-landing-001` and
`quicker-landing-heldout-001` passed. Neural request-to-stable-contact time
dropped from approximately 2.0 s to **1.36 s** at seed 420 and **1.30 s** at
held-out seed 424 / wing phase 0.8. Both resumed walking with zero landing
assistance after release, maintained final upright cosine >0.995, and had
post-release displacement 22.55 / 34.48 mm. Earlier slower results below remain
historical evidence, not overwritten by the faster controller.

The app logs `landing_assistance_force_torque` separately from total external
forces. The pre-existing capped environmental wind proxy remains active; a
nonzero wind force is not hidden landing assistance. Standalone landing trials
use no such environment force and verify a zero full force vector after release.

The fly stays the same body across takeoff, landing and walking. Handoff
qpos/qvel and mass/inertia are verified unchanged; no pose/velocity reset,
teleport, gravity removal or hidden recovery is used.

## Walking boundary correction

[WalkingNavigation](../scripts/fly_walking_navigation.py) supplies a separate
explicitly engineered rolling ground reference to the learned gait. It keeps
the previous straight ground reference until a turn is needed, then curves
inward using measured position and arena bounds. It does not map neural readouts
to heading or relabel gait as connectome control.

The actual 15 s physical ground test `walking-boundary-final-001` passed with
minimum boundary clearance **15.06 mm** and minimum upright cosine **0.9910**,
without pose resets. The emergency boundary stop remains for genuine failures.
Obstacle climbing and arbitrary terrain recovery are not established.

## Physical and causal measurements

External bundles under `results/fly-unified`:

| Final reduced motor trial | Neural request | Stable touchdown | Assistance removed | Stable unassisted walk | Displacement after release |
| --- | ---: | ---: | ---: | ---: | ---: |
| `neural-landing-intact-final-001`, seed 420 / wing phase 0.5 | 0.15 s | 2.1502 s | 3.1502 s | 6,749 steps | 13.09 mm |
| `neural-landing-sham-final-001` | 0.15 s | 2.1502 s | 3.1502 s | 6,749 steps | 13.09 mm |
| `neural-landing-heldout-final-001`, seed 424 / wing phase 0.8 | 0.11 s | 2.1102 s | 3.1102 s | 6,949 steps | 25.37 mm |

These diagnostic trials explicitly initialize airborne. They use an actual
physical visual stimulus and the full neural worker, but are not whole
ground-to-flight-cycle evidence. Intact and scheduled identity sham have
**exactly identical full qpos/qvel/action/force hashes**.

DNp10 spike silencing, visual chemical-output disconnection and no-input
controls produced **no landing request and no landing assistance**. Visual
disconnection retained 4,001 source/network spikes; DN silencing retained
7,590 network spikes; no input was silent. Their straight-flight physical
controls eventually reached the explicit boundary margin—this is not a
successful control landing, and the stop is retained in results.

The full same-browser scene test `brain-surface-final-001` used explicit
upstream input **only for GF takeoff initiation**, then actual habitat
surface expansion, not a finger or injected landing-DN drive:

- Actual landing DNp10 response/request at **1.68 s**.
- Stable touchdown at **3.68 s**.
- Landing assistance release at **4.68 s**.
- **11,601** consecutive stable unassisted walking steps through 7 s.
- Final upright cosine **0.9928**.
- Takeoff and landing-request qpos/qvel preserved; mass/inertia unchanged.
- No flight floor contacts or boundary safety pause.
- All 232 post-release logged intervals have zero landing-assistance vector.

`brain-surface-silencing-001` used the same app input and actual scene but
clamped DNp10 spikes. GF takeoff and flight still passed; it had no request,
touchdown or landing assistance. This distinguishes genuine neural initiation
from a direct surface-to-motor rule.

The stricter repeat `brain-surface-final-002` additionally checks physical
post-release displacement, zero maximum post-release landing assistance and
preserved handoffs directly in the cycle acceptance predicate. **It remains
failed:** external pointer/camera actions and finger toggles caused a second
GF takeoff after the first landing, then another DNp10 request near the run's
end. This is an interactive intervention run, not an untouched controlled
repeat; its scope receipt and input logs preserve that distinction.
Controller presence alone cannot set `landing_validated`.

### Retained failed attempts

- `neural-landing-001`: interval-boundary floating-point tolerance caused
  reference validation to fail; fixed without backdating neural input.
- `neural-landing-002`: weak attitude correction and continued gravity support
  left the body perched on contact, without stable upright touchdown.
- `neural-landing-003`: physical touchdown/walking occurred but summary
  serialization failed; preserved as failed, not promoted to final evidence.
- `brain-linked-browser-001`: shared motor-action cache reused a flight-shaped
  action after walking handoff. Separate walking/flight caches now preserve
  the named-channel contracts.
- `brain-linked-browser-002` / `brain-surface-landing-001`: physical landing
  occurred, but the added ground reference changed initial gait slightly and
  the pre-landing flight uprightness missed its declared threshold. The
  ground reference now preserves the original straight path until needed.

Earlier `engineered-cycle-001` through `-007` remain failed and disabled;
this distinct actual-DN-initiated reduced model does not rewrite those results.

Regression suite: **238 tests reported, seven environment/opt-in skips**,
including real compiled surface expansion/occlusion and pure neural request,
clock, release/contact, reset and walking-boundary invariants. Biological
timing/kinematic calibration is not demonstrated by these engineering checks.

## Same app and continuing limitations

After user approval, the sole live app `interactive-app-011` at
http://127.0.0.1:8840/ uses:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --flight-avoidance --neural-leg-extension \
  --brain-linked-landing --landing-surface-vision \
  --objects /previous/session/objects.json \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/session
```

No automatic demonstration stimulus, takeoff timer, random firing or periodic
landing trigger is enabled. It starts walking with no fabricated DN request.
After GF-triggered flight, surfaces can drive the brain; landing occurs only
if actual DNp10 responds. Lack of response can still yield continued flight.

The browser app and main launcher enforce the centrally defined **8840** port.
Alternate ports, including `0`, fail before starting a physical/neural app.
Interactive dashboard construction also enforces that port; occupying it fails
explicitly rather than opening another version. Low-level read-only HTTP
unit-test fixtures may use ephemeral ports without any fly/brain process.
Future physical browser tests must run sequentially on 8840, with approval
before replacing a live session.

Browser status identifies real DN initiation, assumed motor/vision scope,
touchdown/release time and stable unassisted walking counts. It does not label
the entire walking/flight/landing system “neural controls.”

One bounded stimulus/seed/phase set and one scene-driven cycle do not establish
safe landing from arbitrary velocities, yaw/roll, obstacles, friction or
unavailable surfaces. This reference aims at the current horizontal brake
location and floor height; it is not a validated terrain-aware landing-site
selector. Landing can fail on clutter or terrain. Voluntary takeoff, realistic
state modulation, LPLC3/LPLC4 visual calibration, true VNC/muscle dynamics,
leg proprioception and robust unassisted whole-animal behavior remain open.
