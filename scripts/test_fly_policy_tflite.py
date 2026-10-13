"""Compare secure TFLite policies with source-version mean-action fixtures."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np

from datasets import CATALOG
from fly_policy import (
    TFLITE_PARITY_TOLERANCE,
    TFLITE_POLICY_RELATIVE_PATH,
    PublishedMotorPolicy,
    prepare_tflite_policy,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(data_dir: Path) -> dict:
    directory = data_dir.expanduser().resolve() / TFLITE_POLICY_RELATIVE_PATH
    receipt_path = directory / "conversion.json"
    receipt = json.loads(receipt_path.read_text())
    parity = receipt["parity_inputs"]
    parity_path = directory / parity["filename"]
    if (
        parity_path.is_symlink()
        or not parity_path.is_file()
        or parity_path.stat().st_size != parity["size_bytes"]
        or sha256_file(parity_path) != parity["sha256"]
    ):
        raise ValueError("Parity input fixture failed its conversion receipt checks")

    results = {}
    with np.load(parity_path, allow_pickle=False) as fixture:
        for family, model_record in receipt["models"].items():
            model_path = prepare_tflite_policy(data_dir, CATALOG, family, require_parity=False)
            names = [str(name) for name in fixture[f"{family}_input_names"]]
            expected = fixture[f"{family}_expected"]
            policy = PublishedMotorPolicy(model_path)
            if len(names) != len(policy.inputs) or set(names) != set(policy.inputs):
                raise ValueError(f"{family} converted input contract disagrees with parity fixture")
            if expected.shape[1:] != tuple(model_record["output_shape"]):
                raise ValueError(f"{family} converted output contract disagrees with parity fixture")
            actual = []
            for sample_index in range(len(expected)):
                observation = {
                    name: fixture[f"{family}_input_{input_index}"][sample_index, 0]
                    for input_index, name in enumerate(names)
                }
                actual.append(policy.mean_action(observation)[0])
            actual = np.stack(actual)
            if not np.isfinite(actual).all() or not np.isfinite(expected).all():
                raise ValueError(f"{family} parity fixture contains non-finite actions")
            clipped_error = np.abs(np.clip(actual, -1, 1) - np.clip(expected, -1, 1))
            raw_error = np.abs(actual - expected)
            max_clipped_error = float(clipped_error.max())
            if max_clipped_error > TFLITE_PARITY_TOLERANCE:
                raise ValueError(
                    f"{family} clipped mean-action parity exceeded "
                    f"{TFLITE_PARITY_TOLERANCE}: {max_clipped_error}"
                )
            results[family] = {
                "cases": len(expected),
                "action_size": int(actual.shape[1]),
                "max_raw_abs_error": float(raw_error.max()),
                "max_clipped_abs_error": max_clipped_error,
                "model_sha256": model_record["sha256"],
            }

    return {
        "schema_version": 1,
        "status": "passed",
        "conversion_sha256": sha256_file(receipt_path),
        "parity_inputs_sha256": parity["sha256"],
        "runtime": {
            "tensorflow_cpu": importlib.metadata.version("tensorflow-cpu"),
            "python": __import__("sys").version.split()[0],
        },
        "tolerance_clipped_canonical_action": TFLITE_PARITY_TOLERANCE,
        "results": results,
        "validated_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.data_dir)
    destination = args.data_dir.expanduser().resolve() / TFLITE_POLICY_RELATIVE_PATH / "parity-validation.json"
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite parity validation: {destination}")
    with destination.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    for family, result in report["results"].items():
        print(
            f"{family}: {result['cases']} cases, max clipped action error "
            f"{result['max_clipped_abs_error']:.9g}"
        )
    print(f"Parity passed: {destination}")


if __name__ == "__main__":
    main()
