"""Verified published policy assets and explicit inference/action conversion."""

import hashlib
import json
import math
import stat
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
        import tensorflow as tf

        if tf.config.threading.get_intra_op_parallelism_threads() != 1:
            tf.config.threading.set_intra_op_parallelism_threads(1)
        if tf.config.threading.get_inter_op_parallelism_threads() != 1:
            tf.config.threading.set_inter_op_parallelism_threads(1)
        import tensorflow_probability as tfp

        # Public exports are lazy; resolving these registers the SavedModel's types.
        _ = tfp.distributions.Independent, tfp.distributions.Normal

        self.tf = tf
        self.module = tf.saved_model.load(str(directory))
        self.mean_policy = tf.function(
            lambda observation: self.module(observation).mean(), autograph=False
        )

    def action(self, observation, specification):
        import numpy as np

        batched = {}
        for name, value in observation.items():
            array = np.asarray(value, dtype=np.float32)
            if not np.isfinite(array).all():
                raise ValueError(f"Non-finite policy observation: {name}")
            batched[name] = self.tf.convert_to_tensor(array[None, ...])
        mean = self.mean_policy(batched).numpy()
        if mean.shape != (1, *specification.shape):
            raise ValueError("Published policy output does not match motor action specification")
        return canonical_to_physical(mean[0], specification.minimum, specification.maximum)


PublishedFlightPolicy = PublishedMotorPolicy
