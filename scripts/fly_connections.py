"""Read-only, version-matched chemical contact inspection with bounded pages."""

import hashlib
import json
import re
import tempfile
from pathlib import Path


FILES = ("edges.npy", "incoming.npy", "in_offsets.npy", "out_offsets.npy")


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def ids_digest(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def write_index(directory, table, neuron_ids, commit, source_sha256):
    import numpy as np

    pre = np.asarray(table["Presynaptic_Index"], dtype=np.int64)
    post = np.asarray(table["Postsynaptic_Index"], dtype=np.int64)
    contacts = np.asarray(table["Connectivity"], dtype=np.int64)
    signed = np.asarray(table["Excitatory x Connectivity"], dtype=np.int64)
    ids = np.asarray(neuron_ids, dtype=np.int64)
    if (
        any(len(column) != len(pre) for column in [post, contacts, signed])
        or np.any(pre < 0) or np.any(pre >= len(ids))
        or np.any(post < 0) or np.any(post >= len(ids))
        or np.any(contacts <= 0) or np.any(contacts > np.iinfo(np.uint32).max)
        or np.any(signed < np.iinfo(np.int32).min) or np.any(signed > np.iinfo(np.int32).max)
        or np.any(np.abs(signed) > contacts)
    ):
        raise ValueError("Invalid connection indices or contact counts")
    if (
        np.any(ids[pre] != np.asarray(table["Presynaptic_ID"], dtype=np.int64))
        or np.any(ids[post] != np.asarray(table["Postsynaptic_ID"], dtype=np.int64))
    ):
        raise ValueError("Connection indices do not match verified neuron identities")
    edges = np.empty(len(pre), dtype=[("pre", "<u4"), ("post", "<u4"), ("contacts", "<u4"), ("signed", "<i4")])
    edges["pre"], edges["post"], edges["contacts"], edges["signed"] = pre, post, contacts, signed
    if np.any(pre[1:] < pre[:-1]):
        edges = edges[np.argsort(pre, kind="stable")]
    np.save(directory / "edges.npy", edges, allow_pickle=False)
    np.save(directory / "incoming.npy", np.argsort(edges["post"], kind="stable").astype("<u4"), allow_pickle=False)
    for name, field in [("in", "post"), ("out", "pre")]:
        offsets = np.concatenate(([0], np.cumsum(np.bincount(edges[field], minlength=len(ids)), dtype=np.int64)))
        np.save(directory / f"{name}_offsets.npy", offsets, allow_pickle=False)
    receipt = {
        "schema_version": 1, "upstream_commit": commit, "source_sha256": source_sha256,
        "neuron_ids_sha256": ids_digest(neuron_ids), "neurons": len(ids), "edges": len(edges),
        "files": {name: digest(directory / name) for name in FILES},
    }
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


def ensure_index(data_dir, source, neuron_ids, commit):
    import fcntl
    import pandas as pd

    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Connection index requires an exact upstream commit")
    parent = Path(data_dir) / "derived" / "flywire-630-connections"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / commit
    with (parent / f"{commit}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        source_sha = digest(source)
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix=".building-", dir=parent) as temporary:
                stage = Path(temporary) / "index"
                stage.mkdir()
                table = pd.read_parquet(source, columns=[
                    "Presynaptic_ID", "Postsynaptic_ID", "Presynaptic_Index",
                    "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity",
                ])
                write_index(stage, table, neuron_ids, commit, source_sha)
                stage.rename(target)
        receipt = json.loads((target / "receipt.json").read_text())
        if receipt["source_sha256"] != source_sha:
            raise ValueError("Cached connections disagree with verified source file")
        index = ConnectionIndex(target, neuron_ids, commit)
        return index.directory


class ConnectionIndex:
    def __init__(self, directory, neuron_ids, commit):
        import numpy as np

        self.directory = Path(directory)
        self.ids = list(neuron_ids)
        self.mapping = {value: index for index, value in enumerate(self.ids)}
        self.receipt = json.loads((self.directory / "receipt.json").read_text())
        self.validate_metadata({"neuron_ids": self.ids, "upstream_commit": commit})
        if set(self.receipt["files"]) != set(FILES):
            raise ValueError("Connection index has unexpected files")
        for name in FILES:
            if digest(self.directory / name) != self.receipt["files"][name]:
                raise ValueError(f"Connection index checksum mismatch: {name}")
        self.edges, self.incoming, self.in_offsets, self.out_offsets = [
            np.load(self.directory / name, mmap_mode="r", allow_pickle=False) for name in FILES
        ]

    def validate_metadata(self, metadata):
        if (
            self.receipt["schema_version"] != 1
            or self.receipt["upstream_commit"] != metadata["upstream_commit"]
            or self.receipt["neuron_ids_sha256"] != ids_digest(metadata["neuron_ids"])
        ):
            raise ValueError("Connection index snapshot/identities do not match the live brain")

    def lookup(self, neuron_id, direction, offset=0, limit=25):
        if (
            neuron_id not in self.mapping or direction not in {"incoming", "outgoing"}
            or type(offset) is not int or offset < 0
            or type(limit) is not int or not 1 <= limit <= 100
        ):
            raise ValueError("Select a known string neuron ID, incoming/outgoing direction, offset >= 0 and limit 1..100")
        index = self.mapping[neuron_id]
        offsets = self.in_offsets if direction == "incoming" else self.out_offsets
        start, end = int(offsets[index]), int(offsets[index + 1])
        stop = min(start + offset + limit, end)
        begin = min(start + offset, end)
        rows = self.edges[self.incoming[begin:stop]] if direction == "incoming" else self.edges[begin:stop]
        edges = [{
            "source_id": self.ids[int(row["pre"])], "target_id": self.ids[int(row["post"])],
            "contacts": int(row["contacts"]), "signed_contacts": int(row["signed"]),
        } for row in rows]
        return {
            "neuron_id": neuron_id, "direction": direction, "offset": offset, "limit": limit,
            "total": end - start, "edges": edges, "upstream_commit": self.receipt["upstream_commit"],
            "scope": "Chemical contact counts and upstream assigned signed-contact proxy; not measured conductance or electrical junctions.",
        }
