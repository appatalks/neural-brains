"""Independent event-resolved VNC reference; not a match to historical GPU output."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from datasets import CATALOG, ROOT
from run_flywire_sugar import verified_inputs
from test_bdn2_vnc import load_circuit, parameters, rate_derivative, retained_weight_indices


MOTOR_BODY_ID = "12686"
CASES = ("intact", "sham", "no-drive", "dn-cut", "exc1-cut", "exc2-cut", "inh-cut", "mn-silence")
START_S, STOP_S, DURATION_S, SAMPLE_DT_S = .05, .8, 1., .001


def network_inputs(data_dir, parameter_seed=428):
    import h5py
    import numpy as np

    if type(parameter_seed) is not int or not 0 <= parameter_seed < 2**32:
        raise ValueError("Independent parameter seed must be a nonnegative32bit integer")
    _, _, _, median_size, paths = load_circuit(data_dir)
    with paths["wTable_20250813_DNtoMN_unsorted_withModules.csv"].open() as stream:
        parent = list(csv.DictReader(stream))
    catalog = json.loads(CATALOG.read_text())
    dataset = next(row for row in catalog["datasets"] if row["id"] == "bdn2-vnc-pruning-parameters-zenodo22260924")
    archive = verified_inputs(data_dir, dataset)["DNg100_Stim_Prune.zip"]
    member = "simulations/DNg100_Stim_Prune/hyak/run_id=28965859/ckpt/neuron_params.h5"
    with ZipFile(archive) as zipped:
        content = zipped.read(member)
    with h5py.File(io.BytesIO(content), "r") as saved:
        indices = retained_weight_indices(saved["W_mask"][336], np.array([31, 277, 617, 1167]))
        if len(indices) != 148 or set(indices[4:]) != set(saved["mn_idxs"][...]):
            raise ValueError("Independent reference requires the verified core and all144motor targets")
        rows = [parent[index] for index in indices]
        weights = saved["W"][...][np.ix_(indices, indices)].astype(np.float64)
        ordering = np.argsort(indices)
        restore = np.argsort(ordering)
        variants = {}
        for replicate in (336, 422):
            variants[f"saved-{replicate}"] = {
                target: saved[source][replicate, indices[ordering]][restore].astype(np.float64)
                for target, source in (("tau", "tau"), ("gain", "a"),
                                       ("threshold", "threshold"), ("cap", "fr_cap"))
            }
    variants[f"prospective-{parameter_seed}"] = parameters(
        np.array([float(row["size"]) for row in rows]), parameter_seed, median_size)
    motor = next(index for index, row in enumerate(rows) if row["bodyId"] == MOTOR_BODY_ID)
    if rows[motor]["class"] != "motor neuron" or rows[motor]["motor module"] != "coxa swing":
        raise ValueError("Reference motor output must be exact MANC12686 coxa-swing target")
    provenance = {
        "archive_receipt": json.loads((archive.parent/"receipt.json").read_text()),
        "parameter_member": member, "parameter_member_sha256": hashlib.sha256(content).hexdigest(),
        "matrix_sha256": hashlib.sha256(weights.tobytes()).hexdigest(),
        "parent_annotation_receipt": json.loads((paths["wTable_20250813_DNtoMN_unsorted_withModules.csv"].parent/"receipt.json").read_text()),
        "median_parent_volume": median_size,
    }
    return weights, rows, variants, motor, provenance


def integrate(weights, params, motor, case, method="RK45", tolerance=2e-9):
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.sparse import csr_matrix

    if case not in CASES or method not in ("RK45", "DOP853") or not 0 < tolerance <= 2e-9:
        raise ValueError("Reference requires a declared case, solver and tolerance")
    n = len(weights)
    if (np.shape(weights) != (n, n) or n < 4 or not np.isfinite(weights).all()
            or type(motor) is not int or not 4 <= motor < n
            or set(params) != {"tau", "gain", "threshold", "cap"}):
        raise ValueError("Invalid independent reference connectivity/output/parameters")
    for value in params.values():
        if np.shape(value) != (n,) or not np.isfinite(value).all() or (np.asarray(value) <= 0).any():
            raise ValueError("Reference parameters must be positive finite vectors")
    recurrent = np.array(weights, dtype=np.float64, copy=True)
    cut = {"dn-cut": 0, "exc1-cut": 1, "exc2-cut": 2, "inh-cut": 3}.get(case)
    if cut is not None:
        recurrent[cut] = 0
    weighted = csr_matrix(.03*recurrent.T)
    drive = np.zeros(n)
    if case != "no-drive":
        drive[0] = 250.

    def rhs(_time, state, applied):
        derivative = rate_derivative(state, applied, weighted, params)
        if case == "mn-silence":
            derivative[motor] = -state[motor]/params["tau"][motor]
        return derivative

    times = np.arange(round(DURATION_S/SAMPLE_DT_S)+1)*SAMPLE_DT_S
    output = np.empty((n, len(times)))
    state = np.zeros(n)
    for start, end, applied in ((0., START_S, np.zeros(n)),
                               (START_S, STOP_S, drive), (STOP_S, DURATION_S, np.zeros(n))):
        result = solve_ivp(rhs, (start, end), state, args=(applied,), method=method,
                           rtol=tolerance, atol=tolerance*.0025, max_step=.0002, dense_output=True)
        if not result.success:
            raise RuntimeError(f"Independent reference solver failed: {result.message}")
        selected = (times >= start) & (times <= end)
        output[:, selected] = result.sol(times[selected])
        state = result.y[:, -1]
    if not np.isfinite(output).all() or output.min() < -1e-8:
        raise RuntimeError(f"Reference produced invalid raw rates (minimum={output.min()}); no clipping/fallback applied")
    return times, output


def run(data_dir, output, parameter_seed=428):
    import numpy as np
    import scipy

    data_dir, output = data_dir.expanduser().resolve(), output.expanduser().resolve()
    if any(path == ROOT or ROOT in path.parents for path in (data_dir, output)) or output.exists():
        raise ValueError("Choose verified external data and a new external reference output")
    weights, rows, variants, motor, provenance = network_inputs(data_dir, parameter_seed)
    output.mkdir(parents=True)
    protocol = {
        "schema_version": 1, "reference_kind": "independent-event-resolved-float64",
        "scope": "New numerical baseline for measured MANC topology and assumed published rate dynamics; not archived GPU parity, brain LIF spikes, calibrated physiology or gait.",
        "variants": list(variants), "cases": CASES, "prospective_parameter_seed": parameter_seed,
        "body_ids": [row["bodyId"] for row in rows], "motor_body_id": MOTOR_BODY_ID,
        "motor_index": motor, "duration_s": DURATION_S, "sample_dt_s": SAMPLE_DT_S,
        "stimulus_window_s": [START_S, STOP_S], "stimulus_model_units": 250.,
        "precision": "float64", "solver": "RK45", "rtol": 2e-9, "atol": 5e-12,
        "maximum_step_s": .0002, "clipping": "none",
        "predeclared_checks": [
            "Intact motor response>0 and exactly0before50ms.",
            "Sham and fresh reset replay identical for every cell/time sample.",
            "No-drive silent; DNcut leaves only driven DN state, not motor/interneurons.",
            "Motor clamp exactly0 despite upstream DN activity.",
            "DOP853 and tenfold tighter RK45 differ from intact by<0.001at every sample/cell.",
        ],
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
        "provenance": provenance,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    (output/"status.json").write_text('{"status":"running"}\n')
    checks, results = [], []
    try:
        for name, params in variants.items():
            np.savez_compressed(output/f"{name}-parameters.npz", **params)
            intact = None
            for case in CASES:
                times, rates = integrate(weights, params, motor, case)
                np.savez_compressed(output/f"{name}-{case}.npz", time_s=times, rates=rates)
                row = {"variant": name, "case": case,
                       "maximum_motor_rate": float(rates[motor].max()),
                       "rate_sha256": hashlib.sha256(rates.tobytes()).hexdigest()}
                results.append(row)
                if case == "intact":
                    intact = rates
                    passed = rates[motor].max() > 0 and np.array_equal(
                        rates[:, times <= START_S], np.zeros_like(rates[:, times <= START_S]))
                elif case == "sham":
                    passed = np.array_equal(rates, intact)
                elif case == "no-drive":
                    passed = np.array_equal(rates, np.zeros_like(rates))
                elif case == "dn-cut":
                    passed = rates[0].max() > 0 and np.array_equal(rates[1:], np.zeros_like(rates[1:]))
                elif case == "mn-silence":
                    passed = rates[0].max() > 0 and np.array_equal(rates[motor], np.zeros_like(rates[motor]))
                else:
                    passed = bool(np.isfinite(rates).all())
                checks.append({"variant": name, "case": case, "passed": bool(passed)})
                (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
                print(name, case, row["maximum_motor_rate"], "passed="+str(passed), flush=True)
            for label, method, tolerance in (("independent-integrator", "DOP853", 2e-9),
                                              ("tighter-tolerance", "RK45", 2e-10),
                                              ("fresh-reset-replay", "RK45", 2e-9)):
                _, rates = integrate(weights, params, motor, "intact", method, tolerance)
                difference = float(np.max(np.abs(rates-intact)))
                checks.append({"variant": name, "case": label, "maximum_rate_difference": difference,
                               "passed": difference == 0 if label == "fresh-reset-replay" else difference < .001})
                np.savez_compressed(output/f"{name}-{label}.npz", time_s=times, rates=rates)
        summary = {"status": "passed" if all(check["passed"] for check in checks) else "failed",
                   "checks": checks, "scope": protocol["scope"], "motor_controller_modified": False}
        (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        (output/"status.json").write_text(json.dumps({"status": summary["status"]})+"\n")
        if summary["status"] != "passed":
            raise RuntimeError("Independent reference checks failed; results retained")
        return summary
    except Exception as error:
        (output/"status.json").write_text(json.dumps({"status": "failed", "error": str(error)})+"\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--parameter-seed", type=int, default=428)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.parameter_seed)
