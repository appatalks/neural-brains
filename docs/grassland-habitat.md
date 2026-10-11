# Compact grassland with physical loose objects

The user requested a habitat **25% smaller in width and depth**, more
fly-relevant materials, grass, and objects the fly can interact with.
The new version-3 [grassland scene](../experiments/fly-walking/grassland-habitat.json)
is the unified backend's default. The older planted/legacy scenes are preserved.

## Dimensions and flight

The previous arena was 300 mm wide (150 mm half-size). The grassland is
**225 mm wide and deep**, with 112.5 mm half-size. Each horizontal dimension
is 75% of the original; ground area is 56.25%, not 75%. Existing geometry
retains millimeter scale instead of shrinking the fly or objects.

The engineered flight reference is proportionally reduced from 20 to
**15 cm/s** in this smaller arena. Turn bounds remain 3 rad/s and
12 rad/s². Trials that instead demanded tighter turns at the original speed
passed airborne diagnostics but destabilized the ground-to-flight transition;
they were retained and not deployed. Launch assistance remains 0.3 s, with
the same disclosed force/torque mechanism and no hidden pose resets.

Flight obstacle sampling now covers three horizontal height bands, including
2 mm above/below the body, rather than only the thorax center line. It still
uses privileged physical geometry, not biological vision. Low ground cover
outside the flight corridor is excluded before the existing 32-object memory
budget is checked; dense grass no longer exhausts memory simply by being
visible during takeoff.

Tall flowering plants were moved beside the central travel area after a
wing/vegetation collision appeared in a coupled trial. The scene does not
remove their contact geometry or claim vegetation navigation is solved.

## Environment and interactions

- **70 fixed physical objects**, including 48 grass blades arranged in 16
  clumps, flowering plants, fallen leaves, moss, bark, stones, a wet-soil
  patch, fruit and banana-peel surfaces.
- **14 material definitions** with distinct colors, specularity and
  sliding/torsional/rolling friction.
- A deterministic procedurally generated soil texture on the floor, replacing
  the laboratory grid in this scene. No external assets or unverified texture
  licenses are introduced.
- Directional daylight illuminates the full habitat instead of leaving most
  grassland outside the old localized light pool. It changes rendered lighting,
  not collision shapes, mass, friction or neural encoders.
- **Three loose physical objects:** two seeds and a small leaf-chaff piece,
  each with a free joint, collision shape, declared mass and material.

Grass/leaves are rigid ellipsoid/capsule approximations, not flexible living
plants. Materials and loose-object masses are **explicit engineering
assumptions**, not measured seed, foliage or receptor physiology.

The loose seeds can be physically nudged by legs, body or the external finger.
They are not animated by a script or environmental success rule. Their
position, velocity and actual fly-contact-step counts are logged and shown in
the existing browser status. Static vegetation/fruit can be touched, stood on
or collide with the body, but autonomous terrain climbing, stable landing and
physical feeding remain incomplete.

Fruit sits beside the initial walking route so the flat-ground learned
controller is not immediately forced over an enlarged fruit obstacle. The
[matched feeding config](../experiments/flywire-sugar/grassland-feeding.json)
and odor proxy both use [9, 4, 1] mm. Sugar exposure drives actual existing
neural inputs; this remains a geometric proxy, not proboscis actuation,
nutritional uptake or calibrated odor/taste.

The neural and body models remain unchanged in scope: learned walking/wing
control, GF initiation, the opt-in reduced DNp10 leg pathway, and explicitly
engineered flight avoidance. This habitat is not a claim of organic neural
flight or a complete biological animal.

## Physical validation

[test_grassland_interaction.py](../scripts/test_grassland_interaction.py)
uses actual FlyBody learned walking, not imposed seed motion. In the final
0.8 s contact trial:

| Object | Fly-contact steps | Horizontal displacement |
| --- | ---: | ---: |
| Loose seed A, assumed 0.02 mg | 542 | 6.46 mm |
| Loose seed B, assumed 0.04 mg | 329 | 16.34 mm |
| Leaf chaff | 0 | 0 mm |

Minimum body upright cosine was **0.9929**. Off-path controls had no seed
contacts and zero horizontal seed displacement. Repeating the contact trial
matched the complete qpos/qvel/action hash exactly. No external assistance
or within-trial pose resets were applied.

External final bundle: `results/fly-unified/grassland-contact-final-001`.
These results establish physical object interaction in a bounded learned-gait
experiment, not neurally directed seed manipulation.

The final compact airborne flight trial,
`grassland-flight-final-001`, completed **15 seconds**, with:

- Minimum boundary clearance 12.88 mm.
- Zero fly-floor contacts.
- Minimum thorax height 9.79 mm.
- Minimum upright cosine 0.5138.
- Unchanged body mass/inertia; no external steering force or runtime pose reset.
- Explicit diagonal initial heading and wing phase 0.8.

The coupled ground-to-flight trial `grassland-browser-test-006` passed five
seconds, and `grassland-browser-final-001` repeated the result over **eight
seconds** (36,950 post-assistance flight steps), preserving takeoff qpos/qvel
and body mass/inertia. They had zero
flight-floor contacts, minimum boundary clearance 12.29 mm, minimum flight
height 9.17 mm and minimum upright cosine 0.4108. Takeoff remains assisted,
not a biological muscle decoder. These are engineering thresholds, not
empirical fly equivalence or indefinite stability evidence.

### Failures preserved

- `compact-flight-001`: original-speed/original-turn controller hit the
  smaller arena's boundary. The emergency stop was not disabled.
- `compact-flight-002` and early `grassland-flight-001`/`-002`: tighter turns
  passed already-airborne tests; that did not establish a stable coupled
  takeoff.
- `grassland-contact-001`: seeds moved and replay matched, but both cases
  tumbled into the fruit overlapping the straight walking route. An explicit
  scope correction is retained; later checks require upright walking.
- `grassland-browser-test-001`: too many low plant geometries exhausted the
  flight obstacle budget during launch.
- `grassland-browser-test-002`/`-003`/`-004`, and
  `compact-planted-launch-001`: tighter-turn launch transitions were unstable.
- `grassland-browser-test-005`: lower-speed flight launched successfully but
  later clipped the centrally placed flowering vegetation.

Failed bundles are not overwritten or described as working interactions.

## Schema and safe integration

Version 1 and version 2 scene serialization stays unchanged. Version 3 adds:

- `ground_material`: an explicitly declared material reference.
- `movable_objects`: existing object fields plus `mass_mg`, limited to
  0.001–1000 mg, at most 32 objects. Names, bounds, sizes, mass, materials and
  unknown fields are validated.

FlyBody uses centimeters and grams: all positions/sizes and milligram masses
are explicitly converted. Movable bodies use MuJoCo free joints and
calculated inertia from their declared geometry/mass.

Loose seeds add joints before the fly in the compiled model. The app no
longer assumes the first three global qvel entries belong to the fly; its
wind proxy reads the actual thorax's world velocity. Ground contacts are
likewise filtered to **fly-to-ground** contacts. A resting seed on the floor
cannot be counted as fly landing or as evidence of initial fly contact.

The model's complete dynamic state is transmitted to the independent observer
renderer; moving props, not just the fly, appear in the authoritative world.
Explicit Reset resets the entire physical episode and contact counters.
Loose-object positions/velocities are preserved in telemetry and the final
summary; fixed editor placements remain in the existing saved-object file.

Version-3 scenes require the unified FlyBody backend. Legacy FlyGym and
legacy flight-benchmark entry points reject them explicitly rather than
silently dropping moving objects. Their existing version-1/2 scenes remain
available.

Validation: **231 repository tests reported, seven environment/opt-in skips**,
plus explicit EGL renderer tests. Tests cover old scene roundtrips, new
mass/material/shape validation, compiled free-body mass/collision/soil texture,
food alignment, contact isolation and low-grass memory exclusion.

## Run in the same browser

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --flight-avoidance --neural-leg-extension \
  --data-dir "$FLY_DATA_DIR" --output-dir /new/external/session
```

The unified defaults select the grassland scene, its matched feeding config
and 112.5 mm half-size. Use `--scene`, `--feeding-config` and
`--flight-arena-half-size-mm 150` to reproduce the earlier planted comparison.
Never replace an active session without approval; run only one ongoing app
at http://127.0.0.1:8840/.

The approved sole live session is `results/fly-unified/interactive-app-010`.
The old good-flight run `interactive-app-008` closed by user and its fixed
editor placements were preserved. After visual inspection, the user approved
a separate save/restart for daylight; `interactive-app-009` was stopped before
starting `-010`. The user's latest paused/camera/friction/sugar settings were
restored through logged controls. Restart is an explicitly new physical
episode, not a claimed seamless physics handoff. The pre-restart loose-object
positions/velocities remain in the old telemetry/summary.

Browser verification showed loaded world/eye images, live loose-object
contact readouts and no horizontal page overflow. Both whole-habitat and
close-up images were inspected; daylight improves visibility. This is a
stylized physics habitat, not a photorealistic asset claim.

The editor still places fixed cubes/spheres, not new free bodies. The physical
finger can push the preconfigured seeds. Autonomous grasping, directed food
seeking, flexible vegetation and stable touchdown/walking transitions are
future work, not hidden behind the richer environment.
