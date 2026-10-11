# neural-brains

Building connectome-informed neural and embodied models across species.
The fruit fly is the first active simulation: **127,400 neurons**, physical
walking/flight and live neural inspection in one browser.

**Research prototype:** learned motor control and assisted transitions are not
a complete biological fly.

## Launch the fly model

After [setup](readme-2.md), set `FLY_DATA_DIR` to your verified external data directory:

```bash
MUJOCO_GL=egl .venv-biomechanics/bin/python scripts/fly_habitat.py \
  --backend unified --flight-avoidance --neural-leg-extension \
  --data-dir "$FLY_DATA_DIR" \
  --output-dir "$FLY_DATA_DIR/results/fly-unified/session-$(date +%Y%m%d-%H%M%S)"
```

Open **http://127.0.0.1:8840/** — one instance only. Experimental full landing is off.

[Whitepaper (PDF)](docs/neural-brains-whitepaper.pdf) · [Technical reference](readme-2.md)
