# Central puddle habitat and fullscreen world

## Current defaults

The current scene is the preserved [half-area variant](../experiments/fly-walking/puddle-compact-habitat.json):
**159.099 ×159.099 mm**, exactly half the previous225×225 mm floor area.
Only XY placements and the puddle radius are scaled by1/sqrt(2); the fly,
objects, heights, masses and force units are unchanged. Food exposure regions
are matched in [the compact feeding file](../experiments/flywire-sugar/puddle-compact-feeding.json).
The earlier full-area files below remain reproducible historical versions.
User-edited placements are scaled only with explicit approval.

The main launcher now defaults to the unified backend with brain-guided
walking, brain-linked assisted landing and binary landing-surface input enabled.
These are the explicitly assumed hybrid interfaces, not complete biological
autonomy. Disable them for comparisons with
`--no-brain-guided-walking --no-brain-linked-landing`; surface input defaults off
when landing is disabled or graded vision is selected. Explicit `--backend
walking` retains the legacy walking backend. Low-level research `run()` defaults
remain opt-in.

The new [version-4 scene](../experiments/fly-walking/puddle-habitat.json) preserves
the earlier grassland file and adds:

- Central 28 mm diameter, 0.15 mm deep circular puddle.
- Rigid leaf island, small sugar crystals and a separate free-body leaf.
- Shore fruit, berries, sugar and Gaussian odor/light proxy sources.
- 78 static objects, 4 movable objects and 16 declared materials.
- Explicit dry-soil spawn at (-45, -65, 1.278) mm, approved after island-start
  tests fell. Water/island traversal remains experimental.

Shore props leave a clear central approach. The
[version-2 feeding configuration](../experiments/flywire-sugar/puddle-feeding.json)
matches four spherical taste regions to actual food/sugar placements.
Any overlap requests the original validated 100 Hz feeding stimulus; overlaps
do not add multiple rates. MN9 counts are genuine neural readouts, not nutrient
uptake or physical proboscis actuation. Odor/light proxies are reported scene
sources, not reconstructed neural odor processing, hunger or thirst.

Version 4 walking references follow measured support height with a 50 ms
filter. This is privileged engineering terrain feedback, not proprioceptive
neural physiology. No physical pose is reset during walking. Version 1–3
reference behavior and historical scene files are unchanged.

## Two water modes

**Default rigid prototype:** the water-colored cylinder is a fixed collision
surface with assumed 0.9 sliding friction for controller compatibility. It is
not real wet friction, buoyancy, swimming or liquid contact.

**Experimental fluid forces:** add `--fluid-physics`. The water visual is
noncolliding; the soil floor remains its bed. Dynamic fly collision geometry
and loose objects receive bounded hydrostatic buoyancy and linear/angular drag
inside the declared volume. Native aerodynamic wing geoms are excluded.

[The reduced implementation](../scripts/fly_water.py) uses cm/g/s consistently:
1 mg/mm³ equals 1 g/cm³. Primitive displaced volumes are calculated;
meshes use bounding-box volume. Sphere caps are integrated, other immersion
fractions are vertical-bound approximations, and region edges use geom centers.
Buoyancy torque acts about body COM. Forces are limited to four body weights;
torques use the corresponding bounding-radius limit. Vertical force
linearization is implicit over the actual force-update interval to avoid
energy injection in very light, shallow floating objects.

This is **not CFD**. Waves, flow advection, water conservation, surface tension,
wetting, swimming/drowning and neural water receptors are absent. Biological
inference from this reduced bath is inappropriate. Water forces and scope are
visible in telemetry; none are hidden landing assistance.

## Fullscreen and overlays

Click **Fullscreen ground**. The ground image fills the viewport without
stretching or black bars: edge cropping is reflected in pointer coordinates.
Eye views and the neural map have separate fixed docks on the right. **Neuron
details** opens the scrollable inspector without burying the map. Toggle **Eye overlay** and
**Neural overlay** to clear the view. Controls stay overlaid at the bottom.
Exit with **Exit fullscreen** or the browser's Escape key.

Projection uses the covered source-image rectangle; camera controls remain
independent of physics and brain clocks.
Fullscreen API failures are shown explicitly. All views still come from the
same one server/physics instance, port 8840.

## Validation and retained negative results

- Latest fullscreen layout passes actual viewport/eye/map bounds checks at
  1024×576,720×480 and344×624. Both eye images and the whole fitted map remain
  visible; no panel scrolling is needed to find them.
- User walking boundary pause at7.78s is retained in the stopped interactive
  log. The assumed neural boundary lookahead changes from25 to45mm, without
  direct geometric body steering or removal of the emergency stop.
  `compact-boundary-001` completes10s with minimum boundary clearance22.16mm
  and ground upright0.9190. This is a bounded check, not unlimited navigation.
- `compact-flight-001` passes actual3s flight gates:11,950 unassisted ticks,
  no floor contacts and12.07mm minimum clearance. The smaller arena's existing
  size-proportional learned-wing reference is10.6066cm/s rather than15cm/s.
- Actual native fullscreen entered at 1874×754; both overlays were visible and
  eye-overlay hiding was verified. Deterministic browser tests cover contained
  image coordinates, letterbox rejection, overlay state and fullscreen exit.
- Actual reduced-fluid floating-box equilibrium and exact seeded replay pass,
  with dry zero forces, dissipative drag, unchanged qpos/qvel and finite bounded
  forces. Compiled FlyBody tests cover dynamic cylinder/mesh geometry and leaf
  support surfaces.
- `dry-spawn-rigid-001`: full 6 s main-launcher default run completes, minimum
  upright 0.99153. Corrected `dry-spawn-fluid-002`: 4 s completes with actual
  floating-leaf height 0.20682 mm and vertical velocity effectively zero.
  Its 0.02000 mm³ displacement supplies 0.01962 g*cm/s² buoyancy, balancing
  the assumed 0.02 mg leaf weight.
  These are bounded integration checks, not successful island traversal.
- `dry-spawn-fluid-001` exposed a force-clearing integration bug: only the fly's
  external force was cleared, so loose-leaf water forces accumulated. The entire
  external-force array is now cleared per control tick before recomputation;
  that failed loose-object run remains retained despite its stable fly posture.
- Island-start `default-rigid-001..004` all fail ground stability and are retained.
  Moving props, changing traction and terrain-following references did not
  establish reliable island traversal. The user approved dry-soil spawn instead
  of withholding this experimental environment.
- First explicit floating-force attempt accumulated numerical energy and failed
  the equilibrium test. Implicit vertical linearization fixes that numerical
  issue; the equilibrium tolerances were not relaxed.

Results remain outside Git under `results/puddle-habitat`. No live app is
automatically left running, and historical failures are not overwritten.
Full regression: 312 tests, 9 environment-dependent skips; browser JavaScript
syntax and actual floating-body equilibrium/replay checks pass.
