"""Validate and expose the local-only WormPose reference frame bundle."""

import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import struct
import threading

from datasets import CATALOG, ROOT, select_git_tree


DATASET_ID = "wormpose-reference-frames-v1"
TREE_ID = "sample-frames"
MAX_REFERENCE_BYTES = 5_000_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_reference_bundle(bundle_dir: Path) -> tuple[dict, bytes]:
    bundle_dir = bundle_dir.expanduser()
    if bundle_dir.is_symlink():
        raise ValueError("Worm reference bundle directory must not be a symlink")
    bundle_dir = bundle_dir.resolve()
    if bundle_dir == ROOT or ROOT in bundle_dir.parents:
        raise ValueError("Worm reference frames must remain outside the repository")
    if bundle_dir.is_symlink() or not bundle_dir.is_dir():
        raise FileNotFoundError(f"Worm reference frame bundle is missing: {bundle_dir}")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    datasets = [item for item in catalog["datasets"] if item["id"] == DATASET_ID]
    if len(datasets) != 1:
        raise ValueError("Expected exactly one WormPose reference dataset in the catalog")
    dataset = datasets[0]
    tree = select_git_tree(dataset, TREE_ID)
    receipt_path = bundle_dir / "receipt.json"
    frames_path = bundle_dir / "frames.bin"
    if receipt_path.is_symlink() or frames_path.is_symlink():
        raise ValueError("Worm reference bundle files must not be symlinks")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema_version") != 1
        or receipt.get("dataset_id") != DATASET_ID
        or receipt.get("tree_asset_id") != TREE_ID
        or receipt.get("repository_url") != tree.repository_url
        or receipt.get("commit") != tree.commit
        or receipt.get("path") != tree.path
        or receipt.get("tree_sha1") != tree.tree_sha1
        or receipt.get("file_count") != tree.file_count
        or receipt.get("size_bytes") != tree.size_bytes
        or receipt.get("local_only") is not True
    ):
        raise ValueError("Worm reference receipt does not match its pinned local-only tree")
    if not frames_path.is_file():
        raise FileNotFoundError("Worm reference frame stream is missing")
    frame_bytes = frames_path.read_bytes()
    if len(frame_bytes) > MAX_REFERENCE_BYTES or len(frame_bytes) != tree.size_bytes:
        raise ValueError("Worm reference frame stream exceeds its byte limit or pinned size")
    if hashlib.sha256(frame_bytes).hexdigest() != receipt.get("frames_sha256"):
        raise ValueError("Worm reference frame stream checksum mismatch")

    records = receipt.get("frames")
    if not isinstance(records, list) or len(records) != tree.file_count:
        raise ValueError("Worm reference frame manifest count mismatch")
    expected_offset = 0
    frames = []
    seen_names = set()
    for record in records:
        name = record.get("name")
        size = record.get("size_bytes")
        offset = record.get("offset")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".png")
            or type(size) is not int
            or size < 24
            or type(offset) is not int
            or offset != expected_offset
            or offset + size > len(frame_bytes)
            or name in seen_names
        ):
            raise ValueError("Worm reference frame manifest contains an unsafe range")
        seen_names.add(name)
        payload = frame_bytes[offset:offset + size]
        if payload[:8] != PNG_SIGNATURE:
            raise ValueError(f"Worm reference frame is not PNG data: {name}")
        width, height = struct.unpack(">II", payload[16:24])
        if (
            width < 1 or height < 1
            or width != record.get("width")
            or height != record.get("height")
            or hashlib.sha256(payload).hexdigest() != record.get("sha256")
        ):
            raise ValueError(f"Worm reference frame metadata/checksum mismatch: {name}")
        blob_sha = hashlib.sha1(usedforsecurity=False)
        blob_sha.update(f"blob {size}\0".encode())
        blob_sha.update(payload)
        if blob_sha.hexdigest() != record.get("git_blob_sha1"):
            raise ValueError(f"Worm reference Git blob checksum mismatch: {name}")
        frames.append({
            "name": name,
            "offset": offset,
            "size_bytes": size,
            "width": width,
            "height": height,
        })
        expected_offset += size
    if expected_offset != len(frame_bytes):
        raise ValueError("Worm reference frame manifest does not cover the complete frame stream")

    manifest = {
        "available": True,
        "frame_count": len(frames),
        "size_bytes": len(frame_bytes),
        "frames": frames,
        "source_url": f"{tree.repository_url[:-4]}/tree/{tree.commit}/{tree.path}",
        "source_commit": tree.commit,
        "license_status": dataset["license"]["status"],
        "local_only": True,
        "timing_scope": "Source frame timestamps are not supplied; browser playback pace is a display assumption.",
        "neural_pairing": "These frames are not paired with the Kato2015 neural traces or synthetic foraging model.",
    }
    return manifest, frame_bytes


def composite_reference_frame(raw_pixels, mask_pixels) -> bytes:
    from PIL import Image, ImageChops, ImageFilter

    raw = raw_pixels.convert("L")
    mask = mask_pixels.convert("L")
    if raw.size != mask.size:
        raise ValueError("Raw brightfield image and tracked mask dimensions differ")
    binary_mask = mask.point(lambda value: 255 if value > 8 else 0)
    edge = ImageChops.subtract(binary_mask, binary_mask.filter(ImageFilter.MinFilter(3)))
    tint = Image.new("RGBA", raw.size, (78, 228, 207, 0))
    tint.putalpha(edge.point(lambda value: 220 if value > 10 else 0))
    composite = Image.alpha_composite(raw.convert("RGBA"), tint).convert("RGB")
    output = io.BytesIO()
    composite.save(output, format="PNG", compress_level=2)
    return output.getvalue()


class OpenWormReference:
    def __init__(self, data_dir: Path):
        import h5py

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        datasets = [
            item for item in catalog["datasets"]
            if item["id"] == "openworm-movement-aq2947-20140301"
        ]
        if len(datasets) != 1:
            raise ValueError("Expected exactly one pinned Open Worm movement recording")
        dataset = datasets[0]
        assets = dataset.get("selected_assets", [])
        if len(assets) != 1:
            raise ValueError("Expected one selected raw Open Worm recording")
        asset = assets[0]
        file_path = asset["filename"]
        download_dir = data_dir.expanduser().resolve() / dataset["id"] / (file_path + ".download")
        path = download_dir / file_path
        receipt_path = download_dir / "receipt.json"
        if download_dir.is_symlink() or path.is_symlink() or receipt_path.is_symlink():
            raise ValueError("Open Worm recording paths must not redirect through symlinks")
        if not path.is_file() or not receipt_path.is_file():
            raise FileNotFoundError("The pinned Open Worm movement recording is not acquired")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("dataset_id") != dataset["id"]
            or receipt.get("filename") != asset["filename"]
            or receipt.get("size_bytes") != asset["size_bytes"]
            or receipt.get("upstream_checksum") != asset["checksum"]
            or receipt.get("upstream_checksum_verified") is not True
        ):
            raise ValueError("Open Worm recording receipt does not match the pinned asset")

        md5 = hashlib.md5(usedforsecurity=False)
        sha256 = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                md5.update(chunk)
                sha256.update(chunk)
        expected_md5 = asset["checksum"].removeprefix("md5:")
        if (
            size != asset["size_bytes"]
            or md5.hexdigest() != expected_md5
            or sha256.hexdigest() != receipt.get("sha256")
        ):
            raise ValueError("Open Worm recording failed source checksum verification")

        self._file = h5py.File(path, "r")
        self._lock = threading.Lock()
        required = {"full_data", "mask", "timestamp/time"}
        if not all(name in self._file for name in required):
            self._file.close()
            raise ValueError("Open Worm recording is missing expected video datasets")
        self._raw = self._file["full_data"]
        self._mask = self._file["mask"]
        self._times = self._file["timestamp/time"]
        expected_shape = (21163, 480, 640)
        timestamps = self._times[:]
        reported_fps = float(self._mask.attrs.get("fps", 0))
        expected_fps = float(self._mask.attrs.get("expected_fps", 0))
        timestamp_steps = [
            float(right) - float(left)
            for left, right in zip(timestamps, timestamps[1:])
        ]
        if (
            self._raw.ndim != 3
            or self._raw.shape[1:] != (480, 640)
            or self._mask.shape != expected_shape
            or self._times.shape != (expected_shape[0],)
            or int(self._raw.attrs.get("save_interval", 0)) != 200
            or not math.isclose(reported_fps, 31.25, rel_tol=0, abs_tol=1e-6)
            or not math.isclose(expected_fps, 30.0, rel_tol=0, abs_tol=1e-6)
            or self._raw.shape[0] != (self._mask.shape[0] - 1) // 200 + 1
            or any(not math.isfinite(float(value)) for value in timestamps)
            or any(float(right) < float(left) for left, right in zip(timestamps, timestamps[1:]))
        ):
            self._file.close()
            raise ValueError("Open Worm recording has an unexpected image or timing shape")
        self._path = path
        self._raw_stride = int(self._raw.attrs["save_interval"])
        self.manifest = {
            "available": True,
            "source": "Open Worm Movement Database · Zenodo 1201382",
            "doi": "10.5281/zenodo.1201382",
            "license": dataset["license"],
            "attribution": (
                "Zenodo creators: Celine N. Martineau and Ellen A. A. Nollen; "
                "the record description's `who` field also lists Bora Baskaner"
            ),
            "worm": "AQ2947 / CGC N2 (Bristol, UK), adult hermaphrodite, day 8",
            "food": "OP50 on NGM agar (source recording)",
            "arena": "35 mm petri dish",
            "mask_frame_count": int(self._mask.shape[0]),
            "source_fps": reported_fps,
            "expected_fps": expected_fps,
            "duration_s": float(self._times[-1]),
            "resolution_px": [int(self._raw.shape[2]), int(self._raw.shape[1])],
            "raw_image_snapshot_count": int(self._raw.shape[0]),
            "raw_image_snapshot_stride_frames": self._raw_stride,
            "timestamp_median_step_s": statistics.median(timestamp_steps),
            "timestamp_duplicate_steps": sum(step == 0 for step in timestamp_steps),
            "timestamp_nonuniform_steps": sum(
                not math.isclose(step, 1 / reported_fps, rel_tol=0, abs_tol=1e-6)
                for step in timestamp_steps
            ),
            "scope": "Raw brightfield snapshots and recorded segmentation mask; independent of the synthetic foraging model and Kato calcium traces.",
        }

    def render_frame(self, frame_index: int) -> tuple[bytes, dict]:
        from PIL import Image

        if type(frame_index) is not int or not 0 <= frame_index < self.manifest["mask_frame_count"]:
            raise ValueError("Reference frame index is outside the pinned recording")
        raw_index = min(frame_index // self._raw_stride, self._raw.shape[0] - 1)
        with self._lock:
            raw_pixels = self._raw[raw_index]
            mask_pixels = self._mask[frame_index]
            source_time = float(self._times[frame_index])
            raw_source_time = float(self._times[raw_index * self._raw_stride])
        raw_image = Image.fromarray(raw_pixels, mode="L")
        mask_image = Image.fromarray(mask_pixels, mode="L")
        return composite_reference_frame(raw_image, mask_image), {
            "mask_frame": frame_index,
            "source_time_s": source_time,
            "raw_snapshot": raw_index,
            "raw_snapshot_time_s": raw_source_time,
        }

    def close(self) -> None:
        self._file.close()
