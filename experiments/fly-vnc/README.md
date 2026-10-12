# Isolated VNC numerical experiments

This is a CPU-only research environment for the published BDN2 VNC
rate-model comparison. It does not replace the Brian brain environment,
FlyBody environment or physical walking controller.

Python3.10 is used. The source manifest specifies Diffrax0.7.0 and permits
JAX0.6.2; these are pinned here along with numerical dependencies.
The original simulation logs identify four NVIDIA L40S GPUs and a2025-09-08
run date, but not exact installed package or CUDA versions. This CPU
environment is not claimed to be the author's exact execution environment.

```bash
uv venv --python .venv/bin/python .venv-vnc
uv pip install --python .venv-vnc/bin/python \
  -r experiments/fly-vnc/requirements.lock.txt

JAX_PLATFORMS=cpu JAX_ENABLE_X64=false .venv-vnc/bin/python \
  scripts/test_bdn2_vnc.py --archived-parameters --solver diffrax \
  --data-dir "${FLY_DATA_DIR:?Set verified external storage}" \
  --output-dir "$FLY_DATA_DIR/results/walking-paths/native-$(date +%Y%m%d-%H%M%S)"
```

Inputs must already be explicitly acquired and checksum/receipt validated.
Every output must be new and outside Git. This runner never downloads datasets
or starts an interactive app. It exits unsuccessfully when the declared
scientific gates fail; a failed result is not automatically repaired by gain
changes or weaker thresholds.

The loader uses `neuron_params.h5/W_mask` for connectivity. The separate
`*_mini_circuits.npz` marks output activity above0.01 and is used only to
select cases, never to zero connections.

Additional bounded diagnostics:

- `--dense-parent --intact-only`: full4,604-state dense operator comparison;
  this is not a causal control suite.
- `--all-motor-targets`: source core-plus-all144-motor experiment using the
  first four saved parameter rows. It does not compare a different graph
  against archived pruned rates.
- `--full-network --dense-parent --intact-only`: first four saved parameter
  rows on the unpruned4,604-cell parent circuit. This is a motor-output
  diagnostic, not source rate conformance or biological gait validation.

Successful finite Diffrax output uses the published0..1000 postprocessing.
Every negative/abovebound raw count and raw extrema are recorded, along with
solver steps and package versions. Non-finite output fails explicitly; the
source's non-finite-to-zero fallback is deliberately not reproduced.

Validation:

```bash
JAX_PLATFORMS=cpu JAX_ENABLE_X64=false PYTHONPATH=tests \
  .venv-vnc/bin/python -m unittest test_bdn2_vnc_protocol
```

See [current results and retained failures](../../docs/bdn2-vnc-reproduction.md).

## Independent reference and physical joint probe

The user-approved separate [independent reference](../../docs/independent-vnc-joint.md)
uses float64, explicit stimulus boundaries, two integrators and causal/replay
checks. It is not an archived GPU match. Run `scripts/vnc_reference.py` here,
then use the existing flight environment for `scripts/test_vnc_joint.py`.
The latter is an externally tethered, assumed single-joint torque interface;
it does not enable brain-spike gait or change the habitat launcher.

The [subsequent genuine brain packet test](../../docs/brain-spike-joint-test.md)
uses the original Brian environment to export verified BDN2 counts, then the
existing flight environment for the assumed relay/bench. Neural controls pass;
the full coupled scientific protocol fails and is not enabled in the app.

[test_relay_sensitivity.py](../../scripts/test_relay_sensitivity.py) runs a
separately frozen uncertainty grid, matched FG activation events and new
held-out seeds. Its first selected candidate still fails one held-out motion
gate; see [the full evidence](../../docs/relay-uncertainty-test.md).
Relay overrides are research parameters only; default40ms/62.5 behavior and
normal habitat controls are unchanged.
