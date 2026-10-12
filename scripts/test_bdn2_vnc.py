"""Bounded numerical reproduction of a published BDN2-driven VNC rate circuit."""

import argparse
import csv
import hashlib
import io
import importlib.metadata
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from datasets import CATALOG, ROOT
from run_flywire_sugar import verified_inputs


DATASET = "bdn2-manc-t1l-minicircuit-20241118"
CASES = ("intact", "sham", "no-drive", "dn-cut", "exc1-cut", "exc2-cut", "inh-cut")


def load_circuit(data_dir):
    import numpy as np

    catalog = json.loads(CATALOG.read_text())
    dataset = next(row for row in catalog["datasets"] if row["id"] == DATASET)
    paths = verified_inputs(data_dir, dataset)
    weights = np.load(paths["W_20241118_T1Lminicircuit.npy"], allow_pickle=False)
    with paths["wTable_20241118_T1Lminicircuit.csv"].open() as stream:
        rows = list(csv.DictReader(stream))
    if weights.shape != (123, 123) or len(rows) != 123 or not np.isfinite(weights).all():
        raise ValueError("Pinned reduced VNC matrix/table shape or values disagree")
    if [row["minimalWidx"] for row in rows] != [str(index) for index in range(123)]:
        raise ValueError("VNC table ordering does not match matrix indices")
    if len({row["bodyId"] for row in rows}) != len(rows):
        raise ValueError("VNC body IDs must be unique")
    if [row["bodyId"] for row in rows[:4]] != ["10093", "10707", "11751", "13905"]:
        raise ValueError("Published BDN2/CPG identities differ from the selected circuit")
    if any(row["class"] != "motor neuron" for row in rows[4:]):
        raise ValueError("Reduced circuit must contain only motor targets after its four core cells")
    sizes = np.array([float(row["size"]) for row in rows])
    if not np.isfinite(sizes).all() or (sizes <= 0).any():
        raise ValueError("VNC size scaling requires finite positive measured volumes")
    if np.any(weights[3] > 0) or np.any(weights[:3] < 0) or np.any(weights[4:, :4]):
        raise ValueError("Reduced CPG signs or absence of motor-to-core feedback differ")
    with paths["wTable_20250813_DNtoMN_unsorted_withModules.csv"].open() as stream:
        parent = list(csv.DictReader(stream))
    parent_by_id = {row["bodyId"]: row for row in parent}
    if len(parent) != 4604 or len(parent_by_id) != len(parent):
        raise ValueError("Published parent normalization table identity/count mismatch")
    parent_sizes = np.array([float(row["size"]) for row in parent])
    if not np.isfinite(parent_sizes).all() or (parent_sizes <= 0).any():
        raise ValueError("Parent normalization requires finite positive volumes")
    for row, size in zip(rows, sizes):
        if row["bodyId"] not in parent_by_id or float(parent_by_id[row["bodyId"]]["size"]) != size:
            raise ValueError("Reduced-to-parent identity/volume correspondence differs")
    return weights, rows, sizes, float(np.median(parent_sizes)), paths


def parameters(sizes, seed_value=None, reference_size=None):
    import numpy as np
    from scipy.stats import truncnorm

    sizes = np.asarray(sizes)
    reference_size = float(np.median(sizes)) if reference_size is None else reference_size
    if (sizes.ndim != 1 or not len(sizes) or not np.isfinite(sizes).all()
            or (sizes <= 0).any() or not np.isfinite(reference_size) or reference_size <= 0):
        raise ValueError("VNC parameter scaling requires finite positive volumes and reference")
    size_scale = sizes/reference_size
    if seed_value is None:
        return {
            "tau": np.full(len(sizes), .02), "gain": 1/size_scale,
            "threshold": 7.5*size_scale, "cap": np.full(len(sizes), 200.),
        }
    rng = np.random.default_rng(seed_value)
    sampled = [
        truncnorm.rvs(-mean/std, 100, loc=mean, scale=std, size=len(sizes), random_state=rng)
        for mean, std in ((.02, .002), (1., .1), (7.5, .6), (200., 10.))
    ]
    return {"tau": sampled[0], "gain": sampled[1]/size_scale,
            "threshold": sampled[2]*size_scale, "cap": sampled[3]}


def rate_derivative(state, applied, weighted, params, array_module=None):
    if array_module is None:
        import numpy as array_module

    total = applied+weighted@state
    activated = array_module.maximum(params["cap"]*array_module.tanh(
        params["gain"]/params["cap"]*(total-params["threshold"])), 0.)
    return (activated-state)/params["tau"]


def simulate(weights, params, case, tolerance=2e-6, duration=2.):
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.sparse import csr_matrix

    if case not in CASES or not 0 < tolerance <= 2e-6 or duration not in (1., 2.):
        raise ValueError("Use a declared VNC case and the published or stricter solver tolerance")
    recurrent = weights.copy()
    cut = {"dn-cut": 0, "exc1-cut": 1, "exc2-cut": 2, "inh-cut": 3}.get(case)
    if cut is not None:
        recurrent[cut, :] = 0
    weighted = csr_matrix(.03*recurrent.T)
    drive = np.zeros(len(weights))
    if case != "no-drive":
        drive[0] = 250.

    def rhs(_time, state, applied):
        return rate_derivative(state, applied, weighted, params)

    times = np.arange(round(duration*1000)+1, dtype=float)*.001
    state = np.zeros(len(weights))
    output = np.empty((len(weights), len(times)))
    for start, end, applied in ((0., .02, np.zeros_like(drive)),
                               (.02, duration-.001, drive),
                               (duration-.001, duration, np.zeros_like(drive))):
        selection = (times >= start) & (times <= end)
        result = solve_ivp(rhs, (start, end), state, args=(applied,), method="RK45",
                           rtol=tolerance, atol=5e-9, dense_output=True, max_step=.0001)
        if not result.success:
            raise RuntimeError(f"VNC integration failed: {result.message}")
        output[:, selection] = result.sol(times[selection])
        state = result.y[:, -1]
    if not np.isfinite(output).all() or (output < -1e-6).any():
        raise RuntimeError(f"VNC integration produced invalid rate values (minimum={output.min()}); no zero fallback applied")
    return times, output


def simulate_diffrax(weights, params, case, parent_indices, parent_params, duration=1., dense_parent=False):
    import diffrax
    import jax
    import jax.numpy as jnp
    import numpy as np

    if jax.default_backend() != "cpu" or jax.config.jax_enable_x64:
        raise ValueError("Published VNC comparison requires explicit CPU and float32 JAX")
    if case not in CASES or duration != 1.:
        raise ValueError("Native archived comparison requires a declared case and one second")
    if (np.ndim(weights) != 2 or np.shape(weights)[0] != np.shape(weights)[1]
            or len(weights) < 4 or not np.isfinite(weights).all()):
        raise ValueError("Native solver requires a finite square circuit with the four core cells")
    keys = {"tau", "gain", "threshold", "cap"}
    if set(params) != keys or set(parent_params) != keys:
        raise ValueError("Native solver requires exactly tau, gain, threshold and cap parameters")
    indices = np.asarray(parent_indices)
    if (indices.shape != (len(weights),) or len(set(indices.tolist())) != len(indices)
            or indices.dtype.kind not in "iu" or indices.min() < 0 or indices.max() >= 4604
            or any(np.shape(value) != (4604,) for value in parent_params.values())):
        raise ValueError("Native solver requires verified reduced-to-parent mapping and all4604parameter states")
    for key in keys:
        value = np.asarray(params[key])
        parent_value = np.asarray(parent_params[key])
        if (value.shape != (len(weights),) or not np.isfinite(value).all() or (value <= 0).any()
                or not np.isfinite(parent_value).all() or (parent_value <= 0).any()
                or not np.array_equal(value, parent_value[indices])):
            raise ValueError(f"Native {key} parameters are invalid or disagree with parent states")
    recurrent = np.array(weights, dtype=np.float32, copy=True)
    cut = {"dn-cut": 0, "exc1-cut": 1, "exc2-cut": 2, "inh-cut": 3}.get(case)
    if cut is not None:
        recurrent[cut] = 0
    weighted = jnp.asarray(recurrent.T)*jnp.float32(.03)
    selected = jnp.asarray(indices)
    local_params = {key: jnp.asarray(value, dtype=jnp.float32) for key, value in params.items()}
    parent_tau = jnp.asarray(parent_params["tau"], dtype=jnp.float32)
    drive = jnp.zeros(len(weights), dtype=jnp.float32)
    if case != "no-drive":
        drive = drive.at[0].set(250.)
    if dense_parent:
        weighted = jnp.zeros((4604, 4604), dtype=jnp.float32).at[
            selected[:, None], selected[None, :]].set(weighted)
        drive = jnp.zeros(4604, dtype=jnp.float32).at[selected].set(drive)
        local_params = {key: jnp.asarray(value, dtype=jnp.float32) for key, value in parent_params.items()}
    times = jnp.clip(jnp.arange(0., duration+.0005, .001, dtype=jnp.float32), 0., duration)

    def rhs(time, state, _args):
        applied = drive*((time >= .02) & (time <= .999))
        if dense_parent:
            return rate_derivative(state, applied, weighted, local_params, jnp)
        local = rate_derivative(state[selected], applied, weighted, local_params, jnp)
        return (-state/parent_tau).at[selected].set(local)

    result = diffrax.diffeqsolve(
        diffrax.ODETerm(rhs), diffrax.Dopri5(), t0=0., t1=duration, dt0=.001,
        y0=jnp.zeros(4604, dtype=jnp.float32),
        saveat=diffrax.SaveAt(ts=times),
        stepsize_controller=diffrax.PIDController(rtol=2e-6, atol=5e-9),
        max_steps=100000, throw=False,
    )
    if result.result != diffrax.RESULTS.successful:
        raise RuntimeError(f"Native VNC integration failed: {result.result}")
    raw = np.asarray(result.ys[:, selected].T)
    if not np.isfinite(raw).all():
        raise RuntimeError("Native VNC integration produced non-finite rates; no zero fallback applied")
    diagnostics = {
        "raw_minimum_rate": float(raw.min()), "raw_maximum_rate": float(raw.max()),
        "negative_sample_count": int(np.count_nonzero(raw < 0)),
        "above1000_sample_count": int(np.count_nonzero(raw > 1000)),
        "postprocessing": "Published nonnegative/1000 rate clipping after successful finite integration; all corrections explicitly reported. Nonfinite source fallback deliberately not reproduced.",
        "solver_steps": {key: int(value) for key, value in result.stats.items()},
    }
    return np.asarray(times), np.clip(raw, 0., 1000.), diagnostics


def metrics(times, rates, rows):
    import numpy as np
    from scipy.signal import find_peaks

    window = (times >= .3) & (times <= 1.9)
    signals = {}
    for module in ("coxa swing", "coxa stance"):
        selected = [index for index, row in enumerate(rows) if row["motor module"] == module]
        if not selected:
            raise ValueError(f"Missing published motor module {module}")
        signal = rates[selected][:, window].mean(axis=0)
        amplitude = float(np.ptp(signal))
        peaks, _ = find_peaks(signal, prominence=max(.5, amplitude*.1), distance=20)
        signals[module] = {
            "peak_count": len(peaks), "peak_to_peak_rate": amplitude,
            "mean_rate": float(signal.mean()),
            "frequency_Hz": float(1/np.median(np.diff(times[window][peaks]))) if len(peaks) >= 3 else None,
        }
    swing = rates[[i for i, row in enumerate(rows) if row["motor module"] == "coxa swing"]][:, window].mean(axis=0)
    stance = rates[[i for i, row in enumerate(rows) if row["motor module"] == "coxa stance"]][:, window].mean(axis=0)
    correlation = float(np.corrcoef(swing, stance)[0, 1]) if swing.std() > 1e-9 and stance.std() > 1e-9 else None
    return {"modules": signals, "swing_stance_correlation": correlation,
            "maximum_rate": float(rates.max()), "rates_sha256": hashlib.sha256(rates.tobytes()).hexdigest()}


def rhythm_passed(row):
    return (
        all(module["peak_count"] >= 3 and module["peak_to_peak_rate"] > 1.
            for module in row["modules"].values())
        and row["swing_stance_correlation"] is not None
        and row["swing_stance_correlation"] < -.3
    )


def retained_weight_indices(mask, core_indices):
    import numpy as np

    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.shape[0] != mask.shape[1] or mask.dtype != np.bool_:
        raise ValueError("Archived weight mask must be a square Boolean connectivity mask")
    core = np.asarray(core_indices)
    if (core.ndim != 1 or core.dtype.kind not in "iu" or len(set(core.tolist())) != len(core)
            or not len(core) or core.min() < 0 or core.max() >= len(mask)):
        raise ValueError("Archived core indices must be distinct in-range integers")
    retained = np.flatnonzero(mask.any(axis=0) | mask.any(axis=1))
    if not set(core.tolist()) <= set(retained.tolist()):
        raise ValueError("Archived weight mask removes a required core neuron")
    return np.concatenate((core, retained[~np.isin(retained, core)]))


def run(data_dir, output):
    import numpy as np
    import scipy

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose external inputs and a new external result directory")
    weights, rows, sizes, reference_size, paths = load_circuit(data_dir)
    output.mkdir(parents=True)
    protocol = {
        "dataset_id": DATASET, "core_body_ids": [row["bodyId"] for row in rows[:4]],
        "variants": ["mean", "seed-420", "seed-421", "seed-427"], "cases": CASES,
        "prospective_seed": 427, "duration_s": 2., "output_dt_s": .001,
        "drive_window_s": [.02, 1.999], "drive_amplitude_model_units": 250,
        "connection_multiplier": .03, "rtol": 2e-6, "atol": 5e-9,
        "size_normalization_parent_median": reference_size,
        "maximum_solver_step_s": .0001,
        "motor_side_scope": "68 LHS and55 RHS cells in a circuit initiated by left BDN2; motor-to-motor edges preserved.",
        "predeclared_checks": [
            "Intact and sham produce exactly equal sampled rates.",
            "No drive is silent; DN output disconnection prevents premotor/motor activity.",
            "Intact coxa swing and stance each have >=3 peaks and >1 rate-unit peak-to-peak amplitude after300ms.",
            "Intact coxa swing/stance correlation <-0.3.",
            "Disconnecting each of three interneuron outputs eliminates that rhythm criterion.",
            "Mean-parameter result agrees with tenfold tighter solver within 0.05 absolute rate units.",
        ],
        "neuron_parameters": {"tau_mean_s": .02, "tau_std_s": .002, "gain_mean": 1.,
                              "gain_std": .1, "threshold_mean": 7.5, "threshold_std": .6,
                              "cap_mean": 200., "cap_std": 10.},
        "numerical_versions": {"numpy": np.__version__, "scipy": scipy.__version__},
        "input_receipts": {name: json.loads((path.parent/"receipt.json").read_text()) for name, path in paths.items()},
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Published rate-equation/topology numerical adaptation using SciPy RK45 and NumPy truncated-normal samples, not JAX random-seed or bit parity. No FlyWire spikes, proprioception, muscles or whole-body gait implemented.",
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    results, checks = [], []
    started = perf_counter()
    try:
        for variant, seed_value in (("mean", None), ("seed-420", 420), ("seed-421", 421), ("seed-427", 427)):
            params = parameters(sizes, seed_value, reference_size)
            np.savez_compressed(output/(variant+"-parameters.npz"), **params)
            intact_rates = None
            for case in CASES:
                try:
                    times, rates = simulate(weights, params, case)
                except RuntimeError as error:
                    row = {"variant": variant, "case": case, "status": "numerical_failure",
                           "error": str(error)}
                    results.append(row)
                    checks.append({"variant": variant, "case": case, "passed": False,
                                   "error": str(error)})
                    (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                    print(variant, case, str(error), flush=True)
                    continue
                row = {"variant": variant, "case": case, **metrics(times, rates, rows)}
                results.append(row)
                np.savez_compressed(output/f"{variant}-{case}.npz", time_s=times, rates=rates)
                if case == "intact":
                    intact_rates = rates
                    passed = rhythm_passed(row)
                elif case == "sham":
                    passed = intact_rates is not None and np.array_equal(rates, intact_rates)
                elif case == "no-drive":
                    passed = bool(np.array_equal(rates, np.zeros_like(rates)))
                elif case == "dn-cut":
                    passed = bool(np.array_equal(rates[1:], np.zeros_like(rates[1:])))
                else:
                    passed = intact_rates is not None and rhythm_passed(
                        metrics(times, intact_rates, rows)) and not rhythm_passed(row)
                checks.append({"variant": variant, "case": case, "passed": bool(passed)})
                (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                print(variant, case, "passed="+str(passed), row["modules"],
                      "corr="+str(row["swing_stance_correlation"]), flush=True)
            if seed_value is None:
                try:
                    _, tighter = simulate(weights, params, "intact", tolerance=2e-7)
                    difference = float(np.max(np.abs(tighter-intact_rates))) if intact_rates is not None else None
                    checks.append({"variant": variant, "case": "solver-convergence",
                                   "maximum_rate_difference": difference,
                                   "passed": difference is not None and difference < .05})
                except RuntimeError as error:
                    checks.append({"variant": variant, "case": "solver-convergence",
                                   "passed": False, "error": str(error)})
        passed = all(row["passed"] for row in checks)
        summary = {"status": "passed" if passed else "failed", "trials": len(results),
                   "checks": checks, "wall_seconds": perf_counter()-started, "scope": protocol["scope"],
                   "motor_controller_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if not passed:
            raise RuntimeError("Predeclared VNC reproduction checks failed; all results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


def run_archived(data_dir, output, solver="scipy", dense_parent=False, intact_only=False,
                 all_motor_targets=False, full_network=False):
    import h5py
    import numpy as np
    from scipy.signal import find_peaks

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if solver not in {"scipy", "diffrax"}:
        raise ValueError("Choose the declared SciPy or published Diffrax solver")
    if dense_parent and solver != "diffrax":
        raise ValueError("Dense parent comparison requires the native Diffrax solver")
    if full_network and (solver != "diffrax" or all_motor_targets):
        raise ValueError("Full-network experiment requires Diffrax and excludes all-motor-only mode")
    motor_experiment = all_motor_targets or full_network
    cases = ("intact",) if intact_only else CASES
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose external inputs and a new archive-validation directory")
    _, rows, _, _, paths = load_circuit(data_dir)
    catalog = json.loads(CATALOG.read_text())
    dataset = next(row for row in catalog["datasets"] if row["id"] == "bdn2-vnc-pruning-parameters-zenodo22260924")
    archive = verified_inputs(data_dir, dataset)["DNg100_Stim_Prune.zip"]
    with paths["wTable_20250813_DNtoMN_unsorted_withModules.csv"].open() as stream:
        parent = list(csv.DictReader(stream))
    mapping = {row["bodyId"]: index for index, row in enumerate(parent)}
    indices = np.array([mapping[row["bodyId"]] for row in rows])
    prefix = "simulations/DNg100_Stim_Prune/hyak/run_id=28965859/"
    with ZipFile(archive) as zipped:
        content = zipped.read(prefix+"ckpt/neuron_params.h5")
        with np.load(io.BytesIO(zipped.read(prefix+"ckpt/DNg100_Stim_Prune_mini_circuits.npz")),
                     allow_pickle=False) as source:
            activity_masks = np.full(tuple(source["shape"]), source["fill_value"], dtype=bool)
            activity_masks[tuple(source["coords"])] = source["data"]
        if activity_masks.shape != (1024, 4604):
            raise ValueError("Published output-activity mask shape differs")
        selected = [
            index for index, mask in enumerate(activity_masks)
            if mask[indices[:4]].all() and set(np.flatnonzero(mask)) <= set(indices)
        ]
        if len(selected) != 3:
            raise ValueError("Expected three archived circuits wholly contained in the reduced export")
        with np.load(io.BytesIO(zipped.read(prefix+"ckpt/DNg100_Stim_Prune_Rs.npz")),
                     allow_pickle=False) as source:
            if tuple(source["shape"]) != (1, 1024, 4604, 1001):
                raise ValueError("Published retained-rate shape differs")
            reference = {}
            coordinates, values = source["coords"], source["data"]
            for replicate in selected:
                signal = np.zeros((4, 1001))
                for row, neuron in enumerate(indices[:4]):
                    pick = (coordinates[1] == replicate) & (coordinates[2] == neuron)
                    signal[row, coordinates[3, pick]] = values[pick]
                reference[replicate] = signal
        config = zipped.read(prefix+"logs/run_config.yaml")
    with h5py.File(io.BytesIO(content), "r") as saved:
        motor_indices = saved["mn_idxs"][...]
        if saved["W_mask"].shape != (1024, 4604, 4604):
            raise ValueError("Archived weight-mask shape differs")
        if not motor_experiment:
            retained = [retained_weight_indices(saved["W_mask"][replicate], indices[:4])
                        for replicate in selected]
            if any(not np.array_equal(item, retained[0]) for item in retained[1:]):
                raise ValueError("Selected archived cases retain different neuron sets")
            indices = retained[0]
            if len(indices) != 148 or set(indices[4:]) != set(motor_indices):
                raise ValueError("Archived cases must retain four core cells and all144motor targets")
        elif all_motor_targets:
            indices = np.concatenate((indices[:4], motor_indices))
        else:
            indices = np.concatenate((indices[:4], np.flatnonzero(
                ~np.isin(np.arange(4604), indices[:4]))))
        if (motor_indices.shape != (144,) or len(set(motor_indices.tolist())) != 144
                or any(parent[index]["class"] != "motor neuron" for index in motor_indices)):
            raise ValueError("Archived all-motor selection differs from the source target set")
        if len(set(indices.tolist())) != (4604 if full_network else 148):
            raise ValueError("Core and motor populations overlap")
    rows = [parent[index] for index in indices]
    if motor_experiment:
        selected = [0, 1, 2, 3]
    output.mkdir(parents=True)
    protocol = {
        "selected_replicates": selected,
        "selection": "First four archived parameter rows; full4604cell parent circuit without pruning."
        if full_network else "First four archived parameter rows; source keepOnly four core cells plus all144motor targets."
        if all_motor_targets else
        "All output-activity masks with core activity contained in the reduced export; actual HDF5 W_mask selects all148retained states. Activity threshold is not a connectivity mask.",
        "duration_s": 1., "stimulus_window_s": [.02, .999], "source_prefix": prefix,
        "source_parameter_sha256": hashlib.sha256(content).hexdigest(),
        "source_config_sha256": hashlib.sha256(config).hexdigest(),
        "archive_receipt": json.loads((archive.parent/"receipt.json").read_text()),
        "predeclared_checks": [
            "Local core rates agree with the authors' retained core outputs within0.05absolute rate units.",
            "Each three-interneuron core rate has >=3 post300ms peaks with >0.1rate-unit prominence.",
            "Exact sham parity and zero no-input/descending-disconnected core output.",
            "Cutting either excitatory or inhibitory core output eliminates core rhythm.",
        ] if not motor_experiment else [
            "Intact coxa swing/stance meet the unchanged>=3peak/>1amplitude/<-0.3correlation gate.",
            "Exact sham and silent no-drive/DNcut controls.",
            "Core output cuts remove motor rhythmicity only if intact motor gate passes.",
            "No comparison to archived pruned rates is claimed for a different retained network.",
        ],
        "solver": solver,
        "dense_parent_rhs": dense_parent, "cases": cases,
        "all_motor_targets": all_motor_targets,
        "full_network": full_network,
        "selected_body_ids": [row["bodyId"] for row in rows],
        "published_rate_comparison_applicable": not motor_experiment,
        "archive_weight_mask_source": "ckpt/neuron_params.h5/W_mask",
        "activity_mask_role": "Selection of cases only, never used to zero weights",
        "numerical_versions": {name: importlib.metadata.version(name) for name in
                               (("numpy", "scipy", "h5py") if solver == "scipy" else
                                ("numpy", "h5py", "jax", "jaxlib", "diffrax", "equinox", "lineax", "optimistix"))},
        "native_state_count": 4604 if solver == "diffrax" else None,
        "native_postprocessing": "Source clips successful finite output to0..1000; negative/abovebound raw counts and extrema must be reported. Nonfinite outputs fail, never replaced by0.",
        "scope": "Exact saved rate-model parameters and topology. Diffrax uses the source float32 full-parent error norm and stimulus gate; SciPy remains a segmented adaptation. Core rhythm is separate from motor antagonist/whole-body gait validation.",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    checks, results = [], []
    try:
        with h5py.File(io.BytesIO(content), "r") as saved:
            weights = saved["W"][...][np.ix_(indices, indices)].astype(float)
            ordering = np.argsort(indices)
            restore = np.argsort(ordering)
            for replicate in selected:
                params = {
                    target: saved[source][replicate, indices[ordering]][restore].astype(float)
                    for target, source in (("tau", "tau"), ("gain", "a"),
                                           ("threshold", "threshold"), ("cap", "fr_cap"))
                }
                mask = np.ones_like(weights, dtype=bool) if motor_experiment else saved["W_mask"][replicate][np.ix_(indices, indices)]
                circuit = weights*mask
                parent_params = {
                    target: saved[source][replicate, :].astype(float)
                    for target, source in (("tau", "tau"), ("gain", "a"),
                                           ("threshold", "threshold"), ("cap", "fr_cap"))
                }
                intact = None
                for case in cases:
                    diagnostics = None
                    if solver == "scipy":
                        times, rates = simulate(circuit, params, case, duration=1.)
                    else:
                        times, rates, diagnostics = simulate_diffrax(
                            circuit, params, case, indices, parent_params, dense_parent=dense_parent)
                    window = (times >= .3) & (times < .999)
                    peaks = [len(find_peaks(signal[window], prominence=.1, distance=20)[0])
                             for signal in rates[1:4]]
                    oscillating = all(value >= 3 for value in peaks)
                    row = {"replicate": replicate, "case": case, "core_peak_counts": peaks,
                           "motor_metrics": metrics(times, rates, rows)}
                    if diagnostics is not None:
                        row["native_solver_diagnostics"] = diagnostics
                    if case == "intact":
                        intact = rates
                        if motor_experiment:
                            passed = rhythm_passed(row["motor_metrics"])
                        else:
                            error = float(np.max(np.abs(rates[:4]-reference[replicate])))
                            row["maximum_published_core_rate_difference"] = error
                            checks.append({"replicate": replicate, "case": "published-rate-conformance",
                                           "maximum_rate_difference": error, "passed": error < .05})
                            passed = oscillating
                    elif case == "sham":
                        passed = np.array_equal(rates, intact)
                    elif case == "no-drive":
                        passed = bool(np.array_equal(rates, np.zeros_like(rates)))
                    elif case == "dn-cut":
                        passed = bool(np.array_equal(rates[1:], np.zeros_like(rates[1:])))
                    else:
                        passed = (rhythm_passed(metrics(times, intact, rows)) and
                                  not rhythm_passed(row["motor_metrics"])) if motor_experiment else not oscillating
                    checks.append({"replicate": replicate, "case": case, "passed": bool(passed)})
                    results.append(row)
                    np.savez_compressed(output/f"replicate-{replicate}-{case}.npz", time_s=times, rates=rates)
                    (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                    print(replicate, case, "peaks="+str(peaks), "passed="+str(passed),
                          "reference_difference="+str(row.get("maximum_published_core_rate_difference")), flush=True)
        passed = all(row["passed"] for row in checks)
        summary = {"status": "passed" if passed else "failed", "checks": checks,
                   "trials": len(results), "scope": protocol["scope"], "motor_controller_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if not passed:
            raise RuntimeError("Archived VNC core validation failed; results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archived-parameters", action="store_true")
    parser.add_argument("--solver", choices=("scipy", "diffrax"), default="scipy")
    parser.add_argument("--dense-parent", action="store_true",
                        help="Use the full4604state dense dot product for native archived comparison")
    parser.add_argument("--intact-only", action="store_true",
                        help="Bounded intact conformance diagnostic, not the causal control suite")
    parser.add_argument("--all-motor-targets", action="store_true",
                        help="Source keepOnly core+all144motor experiment; not archived-pruned-rate conformance")
    parser.add_argument("--full-network", action="store_true",
                        help="Bounded intact4604cell parent experiment with saved parameters, native solver only")
    args = parser.parse_args()
    if args.archived_parameters:
        run_archived(args.data_dir, args.output_dir, args.solver, args.dense_parent,
                     args.intact_only, args.all_motor_targets, args.full_network)
    elif args.solver != "scipy" or args.dense_parent or args.intact_only or args.all_motor_targets or args.full_network:
        parser.error("Native solver and conformance diagnostics require --archived-parameters")
    else:
        run(args.data_dir, args.output_dir)
