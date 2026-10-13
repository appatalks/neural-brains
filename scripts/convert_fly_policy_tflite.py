"""Convert verified legacy FlyBody policy means to portable TFLite artifacts."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile

import numpy as np

from datasets import CATALOG
from fly_policy import (
    TFLITE_POLICY_FILES,
    prepare_policy,
    verified_archive,
)


PARITY_SEED = 20261013
PARITY_CASES = 32


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parity_observation(specs, rng):
    observation = {
        name: np.zeros((1, *spec.shape[1:]), dtype=np.float32)
        for name, spec in specs.items()
    }
    scales = {
        "walker/ref_displacement": 1.0,
        "walker/gyro": 0.5,
        "walker/accelerometer": 1.0,
        "walker/joints_pos": 0.25,
        "walker/joints_vel": 1.0,
        "walker/appendages_pos": 0.1,
        "walker/touch": 0.2,
        "walker/force": 1.0,
        "walker/actuator_activation": 0.1,
        "walker/velocimeter": 1.0,
    }
    for name, scale in scales.items():
        if name in observation:
            observation[name] = rng.normal(0, scale, observation[name].shape).astype(np.float32)
    quat = rng.normal(size=observation["walker/ref_root_quat"].shape).astype(np.float32)
    observation["walker/ref_root_quat"] = quat / np.linalg.norm(quat, axis=-1, keepdims=True)
    world_zaxis = rng.normal(0, 0.05, observation["walker/world_zaxis"].shape).astype(np.float32)
    world_zaxis[..., 2] += 1
    observation["walker/world_zaxis"] = world_zaxis
    return observation


def convert_policy(tf, module, family: str, rng, parity_payload: dict):
    concrete_functions = module.__call__.concrete_functions
    if len(concrete_functions) != 1:
        raise ValueError(f"Expected one source callable for {family}")
    source = concrete_functions[0]
    args, kwargs = source.structured_input_signature
    if len(args) != 1 or kwargs or not isinstance(args[0], dict):
        raise ValueError(f"Unexpected source input signature for {family}")
    specs = args[0]
    if not specs or any(spec.dtype != tf.float32 or spec.shape.rank < 1 for spec in specs.values()):
        raise ValueError(f"Unexpected source input tensors for {family}")
    if any(any(dim is None for dim in spec.shape[1:]) for spec in specs.values()):
        raise ValueError(f"Unexpected dynamic non-batch input dimension for {family}")

    @tf.function(input_signature=[specs], autograph=False)
    def mean_only(observation):
        return module(observation).mean()

    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [mean_only.get_concrete_function()], module
    )
    model = converter.convert()
    observations = []
    expected = []
    for _ in range(PARITY_CASES):
        observation = parity_observation(specs, rng)
        observations.append(observation)
        expected.append(mean_only(observation).numpy()[0])
    parity_payload[f"{family}_input_names"] = np.asarray(list(specs), dtype=np.str_)
    parity_payload[f"{family}_expected"] = np.stack(expected).astype(np.float32)
    for index, name in enumerate(specs):
        parity_payload[f"{family}_input_{index}"] = np.stack(
            [observation[name] for observation in observations]
        ).astype(np.float32)
    output_shape = list(parity_payload[f"{family}_expected"].shape[1:])
    inputs = [
        {
            "name": name,
            "shape": [int(dim) for dim in specs[name].shape[1:]],
            "dtype": "float32",
        }
        for name in specs
    ]
    return model, {"inputs": inputs, "output_shape": output_shape}


def convert(data_dir: Path) -> Path:
    import tensorflow as tf
    import tensorflow_probability as tfp

    versions = {
        "tensorflow-cpu": importlib.metadata.version("tensorflow-cpu"),
        "tensorflow-probability": importlib.metadata.version("tensorflow-probability"),
    }
    if versions != {"tensorflow-cpu": "2.8.0", "tensorflow-probability": "0.16.0"}:
        raise RuntimeError(
            "Conversion must use the previously verified TensorFlow CPU 2.8.0 / "
            "TensorFlow Probability 0.16.0 environment"
        )
    _ = tfp.distributions.Independent, tfp.distributions.Normal

    archive, dataset_root, asset, dataset = verified_archive(
        data_dir, CATALOG, "trained-fly-policies.zip"
    )
    archive_receipt = json.loads((archive.parent / "receipt.json").read_text())
    data_root = data_dir.expanduser().resolve()
    derived_root = data_root / "derived"
    if derived_root.resolve() != derived_root:
        raise ValueError("Derived data directory must not redirect through symlinks")
    derived_root.mkdir(exist_ok=True)
    destination = data_root / "derived/flybody-flight-policy-mean-tflite-v1"
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite converted policies: {destination}")

    parity_payload = {}
    models = {}
    rng = np.random.default_rng(PARITY_SEED)
    with tempfile.TemporaryDirectory(prefix=".fly-policy-tflite-", dir=derived_root) as temp:
        staging = Path(temp)
        for family, filename in TFLITE_POLICY_FILES.items():
            source_directory = prepare_policy(data_root, CATALOG, family)
            module = tf.saved_model.load(str(source_directory))
            model, contract = convert_policy(tf, module, family, rng, parity_payload)
            model_path = staging / filename
            with model_path.open("xb") as stream:
                stream.write(model)
            models[family] = {
                "filename": filename,
                "size_bytes": len(model),
                "sha256": sha256_file(model_path),
                **contract,
            }

        parity_path = staging / "parity-inputs.npz"
        with parity_path.open("xb") as stream:
            np.savez_compressed(stream, **parity_payload)
        extraction_receipts = {
            "flight": json.loads((dataset_root / "policies/extraction.json").read_text()),
            "walking": json.loads((dataset_root / "policies/extraction-walking.json").read_text()),
        }
        receipt = {
            "schema_version": 1,
            "format": "tensorflow-lite-float32-mean-action",
            "source": {
                "dataset_id": dataset["id"],
                "archive_filename": asset["filename"],
                "upstream_checksum": asset["checksum"],
                "archive_sha256": archive_receipt["sha256"],
                "source_ids": dataset["source_ids"],
                "license": dataset["license"],
                "extracted_policy_members": {
                    family: value["members"] for family, value in extraction_receipts.items()
                },
            },
            "conversion": {
                "tensorflow_cpu": versions["tensorflow-cpu"],
                "tensorflow_probability": versions["tensorflow-probability"],
                "python": os.sys.version.split()[0],
                "converted_utc": datetime.now(timezone.utc).isoformat(),
                "source": "SavedModel distribution mean, exported without quantization",
            },
            "models": models,
            "parity_inputs": {
                "filename": parity_path.name,
                "size_bytes": parity_path.stat().st_size,
                "sha256": sha256_file(parity_path),
                "seed": PARITY_SEED,
                "cases_per_policy": PARITY_CASES,
                "scope": "Synthetic deterministic observations; not physical or biological validation",
            },
        }
        receipt_path = staging / "conversion.json"
        with receipt_path.open("x") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
        staging.replace(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    destination = convert(args.data_dir)
    print(f"Converted flight and walking policies to {destination}")
    print("Run scripts/test_fly_policy_tflite.py in the security-updated flight environment.")


if __name__ == "__main__":
    main()
