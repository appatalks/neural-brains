# Observer-only graphics upgrade

The main habitat now uses an independent
[observer scene](../scripts/fly_graphics.py) for display:

- 8192-pixel shadow map and four-sample offscreen antialiasing.
- Less mirror-like ground material.
- Adjusted observer headlight and body/eye/wing specularity.
- Existing camera panning, top-right eyes, neural status and environment.
- Explicit `_material` habitat materials retain their declared specularity
  and shininess instead of receiving the generic body-material override.

The observer owns a copy of the compiled model and its own display state.
Physical geometry, contacts, mass, inertia and dynamics remain in the
simulation model. Actual retinal rendering still uses that original model:
cosmetic observer changes are not fed into the fly's visual policy.

Physics state and updated terrain/marker positions/colors are copied to the
observer. No second physical simulation runs. Native viewer edits affect
display state, not the body's authoritative state.

## Validation and limits

- Model tests verify original material/light settings are unchanged.
- Body masses, inertia, friction, geometry sizes and joint ranges match.
- Observer state edits cannot change source body position.
- Same-state repeated GPU eye renders already vary by at most one 8-bit
  channel level in a very small number of pixels, even without the upgrade.
  Exact byte parity for retina-driven trajectories is therefore not claimed.
- The separate 0.5-second visual-policy comparisons ended within about
  **1e-7 mm** of each other. Source pose/light/material isolation was exact;
  observed pixel differences matched existing renderer variation.
- The revised rendered preview was visually inspected.

This is incremental lighting/material polish, not photorealistic rendering,
high-resolution meshes, better biological optics, or faster physics.
Shadow size is not a display-FPS guarantee. Hardware/profile measurements
remain necessary before larger textures or renderer migration.

For a lower-level graphics comparison:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_walking.py \
  --headless --seconds 0.5 --vision \
  --scene experiments/fly-walking/habitat.json \
  --controller sensory-demo --observer-graphics \
  --output-dir "$FLY_DATA_DIR/results/fly-walking/observer-graphics-001"
```

The main [habitat launcher](../scripts/fly_habitat.py) enables observer
graphics automatically. Lower-level reference tests omit
`--observer-graphics`; original graphics remain available for comparison.
