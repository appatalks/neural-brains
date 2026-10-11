# Small planted habitat

The reusable [planted scene](../experiments/fly-walking/planted-habitat.json)
adds environmental structure without pretending to solve neural navigation.
It is an optional scene; the original habitat and its benchmarks are preserved.

The later [compact grassland](grassland-habitat.md) is the unified backend's
default: 225 mm width/depth, 48 grass blades, more physical materials, and
free-body seeds/chaff. This page preserves the original version-2 comparison.

## Contents

- Two stylized plants: physical stems and ellipsoid leaves, one with a flower.
- A fruit-colored physical food surface with an explicitly aligned
  [sugar-exposure configuration](../experiments/flywire-sugar/planted-feeding.json).
- Bark-like, smooth and stone landing/contact surfaces.
- Seven explicit color/specularity/friction materials.
- Fruit and flower odor proxies, a light source, and weak wind.

The plants and surfaces are **static physical geometry**, visible to eye
rendering and range/occlusion rays and included in fly contact physics.
Leaves are thick ellipsoids rather than flexible biological foliage.
The material values are engineering settings, not measured bark, cuticle,
stone or fruit biomechanics. Color/specularity are visual; friction affects
contact. Observer graphics preserve these named material properties.

Odors remain Gaussian scalar proxies, not transported chemical species or
calibrated olfactory-neuron inputs. Light affects source rendering and the
existing light proxy, not a validated photoreceptor model. Wind retains the
existing capped thorax-drag approximation; plants do not sway.

The fruit's binary oral-probe exposure gates the actual validated 100 Hz
sugar-GRN stimulus. It is not a geometric surface-receptor intersection,
food consumption, physical proboscis actuation, or measured concentration.
The flower has no sugar input or pollination behavior.

## Run the interactive planted habitat

Set `FLY_DATA_DIR` to the selected external data root, and use a new output
directory. The existing finger/object controls are available within the single browser
app. No separate native ground-world window is needed.

```bash
.venv-biomechanics/bin/python scripts/fly_habitat.py \
  --scene experiments/fly-walking/planted-habitat.json \
  --feeding-config experiments/flywire-sugar/planted-feeding.json \
  --virtual-finger --neural-dashboard \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/flywire-live/planted-session-001"
```

Use the same companion address, **http://127.0.0.1:8840/**. The plant scene
does not require another dashboard or another neural simulation.
The ground world, eyes and neurons are now displayed together there.

T toggles the sugar stimulus, not the visible fruit or its odor proxy.
O toggles the original terrain-bar collection, not planted objects.
The plant scene has no terrain bars, so O does not remove its vegetation.
P pauses, R explicitly resets, C toggles tracking, and Q saves/closes.
H and 1/2/3 retain the existing virtual-finger and small-object editor.
Plants/materials are configured in the scene, not dynamically placed with
that small-object editor.

## Shared geometry and schema

Version 1 remains accepted unchanged. Version 2 adds exactly `materials`
and `objects`; saved run scene files round-trip through the loader.

Version 3 adds explicit ground material and movable-object mass fields for the
unified FlyBody backend. It is not silently substituted into FlyGym; see
[schema and interaction evidence](grassland-habitat.md).

A material defines `name`, four-channel `rgba`, three friction coefficients
(sliding/torsional/rolling), `specular` and `shininess`. All color/specularity
values are in [0, 1]; friction is nonnegative.

A static object defines `name`, `kind`, `position_mm`, `size_mm`,
`pitch_rad` and a declared `material` name:

| Shape | `size_mm` |
| --- | --- |
| Sphere | Radius |
| Capsule | Radius, cylinder half-length along local Z |
| Box | X/Y/Z half-extents |
| Ellipsoid | X/Y/Z radii |

Pitch rotates about Y. Objects must fit within arena XY bounds and remain
above/on the floor. Reserved or duplicate names, undeclared materials,
nonfinite/negative sizes and unknown fields fail explicitly. The limits are
32 materials and 256 objects. Intersections between plant parts are intentional;
arbitrary object-object overlap is not prohibited.

[Shared object definitions](../scripts/fly_environment.py) feed both the
FlyGym walking habitat and the FlyBody flight/unified arenas. Millimeters
are converted to centimeters for FlyBody, including capsule radius/length.
Collision configuration follows each backend's existing mechanism:
explicit ground-contact pairs in FlyGym and collision masks in FlyBody.

The unified prototype accepts `--scene`, but its synthetic controller still
does not autonomously navigate plants or choose landing surfaces.

## Validation (2026-10-10)

- Scene round-trip and original version-1 compatibility tests.
- Shape/material/range validation and explicit sugar/odor alignment tests.
- Matching geometry, material references, rotations and length conversions
  across the walking and flight definitions.
- Both real compiled backends include material assignments and plant contact
  geometry; walking uses explicit fly-to-plant pairs. A ray aimed at the
  same leaf hits that leaf in both backends, verifying visibility/occlusion
  participation rather than merely a decorative mesh.
- Actual walking/eye/neural-worker/dashboard integration completed a bounded
  0.5 s scene run, saved its version-2 scene and previews, and closed cleanly.
  External result: `results/flywire-live/planted-smoke-002`.
- Unified FlyBody walking completed a 0.2 s planted-scene smoke test.
  This is not a vegetation-navigation or successful landing benchmark.
- Full overview and close-up rendering were visually inspected.

Still missing: organic meshes/textures, flexible vegetation, calibrated
material/receptor responses, dynamic food/odor changes, plant editing,
long-session behavior tests and neural navigation/landing control.
