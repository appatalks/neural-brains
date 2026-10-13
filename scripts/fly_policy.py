"""Verified published policy assets and explicit inference/action conversion."""

import hashlib
import json
import math
import stat
import threading
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from datasets import ROOT


POLICY_MEMBERS = {
    "flight/saved_model.pb": 92740,
    "flight/variables/variables.data-00000-of-00001": 662096,
    "flight/variables/variables.index": 800,
}
WALKING_POLICY_MEMBERS = {
    "walking/saved_model.pb": 110102,
    "walking/variables/variables.data-00000-of-00001": 4919480,
    "walking/variables/variables.index": 924,
}
TFLITE_POLICY_RELATIVE_PATH = Path("derived/flybody-flight-policy-mean-tflite-v1")
TFLITE_POLICY_FILES = {"flight": "flight-mean.tflite", "walking": "walking-mean.tflite"}
TFLITE_PARITY_TOLERANCE = 1e-4


def verified_archive(data_dir: Path, catalog_path: Path, filename: str | None = None):
    catalog = json.loads(catalog_path.read_text())
    matches = [d for d in catalog["datasets"] if d["id"] == "flybody-flight-imitation"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one pinned flight dataset")
    dataset = matches[0]
    assets = dataset["selected_assets"]
    if filename is not None:
        assets = [a for a in assets if a["filename"] == filename]
    if not assets or (filename is not None and len(assets) != 1):
        raise ValueError("Expected exactly one selected policy archive")
    asset = assets[0]
    if not asset["checksum"].startswith("md5:"):
        raise ValueError("Flight archive requires a published MD5 checksum")
    root = data_dir.expanduser().resolve() / dataset["id"]
    if root.resolve() == ROOT or ROOT in root.resolve().parents:
        raise ValueError("Resolved flight dataset location must remain outside Git")
    path = root / (asset["filename"] + ".download") / asset["filename"]
    content = path.read_bytes()
    if (
        len(content) != asset["size_bytes"]
        or "md5:" + hashlib.md5(content, usedforsecurity=False).hexdigest() != asset["checksum"]
    ):
        raise ValueError("Flight archive size/upstream checksum mismatch")
    receipt = json.loads((path.parent / "receipt.json").read_text())
    if (
        receipt["sha256"] != hashlib.sha256(content).hexdigest()
        or receipt["source_url"] != asset["url"]
        or receipt["upstream_checksum"] != asset["checksum"]
        or receipt["dataset_id"] != dataset["id"]
    ):
        raise ValueError("Flight archive receipt mismatch")
    return path, root, asset, dataset


def prepare_policy(data_dir: Path, catalog_path: Path, family: str = "flight") -> Path:
    if family not in {"flight", "walking"}:
        raise ValueError("Only verified flight and walking policies are supported")
    members = POLICY_MEMBERS if family == "flight" else WALKING_POLICY_MEMBERS
    path, root, asset, dataset = verified_archive(data_dir, catalog_path, "trained-fly-policies.zip")
    destination = root / "policies"
    if destination.resolve() != destination:
        raise ValueError("Policy extraction path must not redirect through symlinks")
    destination.mkdir(exist_ok=True)
    manifest = {}
    with ZipFile(path) as archive:
        entries = archive.infolist()
        names = [info.filename for info in entries]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate policy archive members")
        for info in entries:
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Unsafe policy archive member")
            if not info.is_dir() and info.filename.startswith(family + "/") and info.filename not in members:
                raise ValueError(f"Unexpected {family} policy file")
        for name, size in members.items():
            if archive.getinfo(name).file_size != size:
                raise ValueError(f"Policy file size mismatch: {name}")
            payload = archive.read(name)
            target = destination / name
            if target.resolve() != target:
                raise ValueError("Policy files must not redirect through symlinks")
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(payload).hexdigest()
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"Previously extracted policy changed: {name}")
            else:
                with target.open("xb") as stream:
                    stream.write(payload)
            manifest[name] = {"size_bytes": len(payload), "sha256": digest}
    provenance = {
        "archive_checksum": asset["checksum"], "members": manifest,
        "license": dataset["license"], "source_ids": dataset["source_ids"],
    }
    record = destination / ("extraction.json" if family == "flight" else "extraction-walking.json")
    if record.is_symlink():
        raise ValueError("Policy provenance must not be a symlink")
    if record.exists():
        if json.loads(record.read_text()) != provenance:
            raise ValueError("Policy provenance changed")
    else:
        with record.open("x") as stream:
            stream.write(json.dumps(provenance, indent=2) + "\n")
    return destination / family


def prepare_tflite_policy(
    data_dir: Path, catalog_path: Path, family: str = "flight", *, require_parity: bool = True
) -> Path:
    if family not in TFLITE_POLICY_FILES:
        raise ValueError("Only verified flight and walking policies are supported")
    archive, _, asset, dataset = verified_archive(data_dir, catalog_path, "trained-fly-policies.zip")
    source_receipt = json.loads((archive.parent / "receipt.json").read_text())
    data_root = data_dir.expanduser().resolve()
    directory = data_root / TFLITE_POLICY_RELATIVE_PATH
    if directory.resolve() != directory:
        raise ValueError("Converted policy directory must not redirect through symlinks")
    receipt_path = directory / "conversion.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise FileNotFoundError(
            "Verified TFLite policies are missing; run scripts/convert_fly_policy_tflite.py "
            "with the pinned legacy policy environment"
        )
    receipt = json.loads(receipt_path.read_text())
    source = receipt.get("source", {})
    if (
        receipt.get("schema_version") != 1
        or source.get("dataset_id") != dataset["id"]
        or source.get("archive_filename") != asset["filename"]
        or source.get("upstream_checksum") != asset["checksum"]
        or source.get("archive_sha256") != source_receipt["sha256"]
    ):
        raise ValueError("Converted policy provenance does not match the verified source archive")
    models = receipt.get("models", {})
    model = models.get(family, {})
    filename = TFLITE_POLICY_FILES[family]
    if model.get("filename") != filename:
        raise ValueError(f"Converted {family} policy provenance is invalid")
    policy_path = directory / filename
    if policy_path.is_symlink() or not policy_path.is_file():
        raise FileNotFoundError(f"Converted {family} policy file is missing")
    payload = policy_path.read_bytes()
    if len(payload) != model.get("size_bytes") or hashlib.sha256(payload).hexdigest() != model.get("sha256"):
        raise ValueError(f"Converted {family} policy checksum mismatch")
    parity = receipt.get("parity_inputs", {})
    parity_path = directory / "parity-inputs.npz"
    if (
        parity.get("filename") != parity_path.name
        or parity_path.is_symlink()
        or not parity_path.is_file()
    ):
        raise ValueError("Converted policy parity inputs are missing")
    parity_payload = parity_path.read_bytes()
    if (
        len(parity_payload) != parity.get("size_bytes")
        or hashlib.sha256(parity_payload).hexdigest() != parity.get("sha256")
    ):
        raise ValueError("Converted policy parity input checksum mismatch")
    if require_parity:
        validation_path = directory / "parity-validation.json"
        if validation_path.is_symlink() or not validation_path.is_file():
            raise ValueError("Converted policy has not passed runtime parity validation")
        validation = json.loads(validation_path.read_text())
        result = validation.get("results", {}).get(family, {})
        if (
            validation.get("status") != "passed"
            or validation.get("conversion_sha256") != hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            or validation.get("parity_inputs_sha256") != parity["sha256"]
            or result.get("model_sha256") != model["sha256"]
            or result.get("max_clipped_abs_error", math.inf) > TFLITE_PARITY_TOLERANCE
        ):
            raise ValueError(f"Converted {family} policy failed its recorded parity validation")
    return policy_path


def canonical_to_physical(action, minimum, maximum):
    import numpy as np

    values = np.asarray(action, dtype=np.float32)
    low = np.asarray(minimum, dtype=np.float32)
    high = np.asarray(maximum, dtype=np.float32)
    if values.shape != low.shape or low.shape != high.shape or not np.isfinite(values).all():
        raise ValueError("Invalid canonical policy action shape or non-finite values")
    if not np.isfinite(low).all() or not np.isfinite(high).all() or (high <= low).any():
        raise ValueError("Invalid policy action bounds")
    clipped = np.clip(values, -1, 1)
    result = low + (clipped + np.float32(1)) * np.float32(0.5) * (high - low)
    return result.astype(np.float64), int(np.count_nonzero(values != clipped))


def tracking_errors(observation) -> tuple[float, float]:
    displacement = observation["walker/ref_displacement"][0]
    quat = observation["walker/ref_root_quat"][0]
    if len(displacement) != 3 or len(quat) != 4:
        raise ValueError("Reference displacement/quaternion shapes are invalid")
    distance = math.sqrt(sum(float(value) ** 2 for value in displacement))
    norm = math.sqrt(sum(float(value) ** 2 for value in quat))
    if not math.isfinite(distance) or not math.isfinite(norm) or norm <= 0:
        raise ValueError("Invalid reference-relative flight observation")
    angle = math.degrees(2 * math.acos(min(1.0, abs(float(quat[0])) / norm)))
    return distance, angle


def evaluate_tracking(records: list[dict], completed_seconds: float, required_seconds: float) -> dict:
    if not records:
        raise ValueError("No control-step records for flight validation")
    if (
        not math.isfinite(completed_seconds) or completed_seconds < 0
        or not math.isfinite(required_seconds) or required_seconds <= 0
    ):
        raise ValueError("Tracking durations must be finite and positive")
    distances = [r["position_error_cm"] for r in records]
    angles = [r["orientation_error_deg"] for r in records]
    if any(not math.isfinite(x) or x < 0 for x in distances + angles):
        raise ValueError("Flight tracking records must be finite and nonnegative")
    rmse = math.sqrt(sum(x*x for x in distances) / len(distances))
    max_angle = max(angles)
    contacts = [r["floor_contacts"] for r in records]
    if any(type(value) is not int or value < 0 for value in contacts):
        raise ValueError("Contact counts must be nonnegative integers")
    floor_contacts = sum(contacts)
    complete = completed_seconds + 1e-9 >= required_seconds
    return {
        "passed": complete and rmse <= 0.1 and max_angle <= 45 and floor_contacts == 0,
        "required_seconds": required_seconds, "duration_complete": complete,
        "rms_position_error_cm": rmse, "maximum_orientation_error_deg": max_angle,
        "floor_contact_steps": floor_contacts,
        "thresholds": {"rms_position_error_cm": 0.1, "maximum_orientation_error_deg": 45, "floor_contact_steps": 0},
        "scope": "Local engineering tracking thresholds, not a paper-derived biological-fidelity criterion.",
    }


class PublishedMotorPolicy:
    def __init__(self, directory: Path):
        import numpy as np
        import tensorflow as tf

        self.model_sha256 = hashlib.sha256(Path(directory).read_bytes()).hexdigest()
        self.interpreter = tf.lite.Interpreter(model_path=str(directory), num_threads=1)
        self.interpreter.allocate_tensors()
        self.inputs = {}
        for detail in self.interpreter.get_input_details():
            name = _tflite_input_name(detail["name"])
            if name in self.inputs:
                raise ValueError(f"Duplicate converted policy input: {name}")
            if detail["dtype"] != np.float32:
                raise ValueError(f"Converted policy input must be float32: {name}")
            self.inputs[name] = detail
        outputs = self.interpreter.get_output_details()
        if len(outputs) != 1 or outputs[0]["dtype"] != np.float32:
            raise ValueError("Converted policy must expose one float32 mean-action output")
        if len(outputs[0]["shape"]) != 2 or outputs[0]["shape"][0] != 1:
            raise ValueError("Converted policy output must have a single batched action")
        self.output = outputs[0]
        self._lock = threading.Lock()

    def mean_action(self, observation):
        import numpy as np

        missing = self.inputs.keys() - observation.keys()
        if missing:
            raise ValueError(f"Missing converted policy observations: {sorted(missing)}")
        with self._lock:
            for name, detail in self.inputs.items():
                values = np.asarray(observation[name], dtype=np.float32)
                expected_shape = tuple(detail["shape"][1:])
                if values.shape != expected_shape or not np.isfinite(values).all():
                    raise ValueError(f"Invalid converted policy observation: {name}")
                self.interpreter.set_tensor(detail["index"], values[None, ...])
            self.interpreter.invoke()
            result = self.interpreter.get_tensor(self.output["index"]).copy()
        if not np.isfinite(result).all():
            raise ValueError("Converted policy returned non-finite mean actions")
        return result

    def action(self, observation, specification):
        mean = self.mean_action(observation)
        if mean.shape != (1, *specification.shape):
            raise ValueError("Published policy output does not match motor action specification")
        return canonical_to_physical(mean[0], specification.minimum, specification.maximum)


def _tflite_input_name(name: str) -> str:
    name = name.removesuffix(":0")
    for prefix in ("serving_default_args_0_walker_", "args_0_walker_"):
        if name.startswith(prefix):
            return "walker/" + name[len(prefix):]
    if name.startswith("args_0/walker/"):
        return name[len("args_0/"):]
    if name.startswith("walker/"):
        return name
    raise ValueError(f"Unexpected converted policy input name: {name}")


PublishedFlightPolicy = PublishedMotorPolicy
