"""List, plan, and download explicitly selected catalog assets outside Git."""

import argparse
import hashlib
import json
import os
from pathlib import PurePosixPath
import sys
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import struct
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "research" / "sources.json"


def component(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"Unsafe path component: {value!r}")
    return value


@dataclass(frozen=True)
class Asset:
    filename: str
    url: str
    size_bytes: int | None = None
    checksum: str | None = None

    def __post_init__(self):
        component(self.filename)
        if self.filename == "receipt.json":
            raise ValueError("Asset filename conflicts with the provenance receipt")
        parsed = urlsplit(self.url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Assets must use public HTTPS URLs without embedded credentials")
        if self.size_bytes is not None and (
            type(self.size_bytes) is not int or self.size_bytes < 1
        ):
            raise ValueError("Asset size must be a positive integer")
        if self.checksum is not None:
            algorithm, separator, digest = self.checksum.partition(":")
            lengths = {"md5": 32, "sha256": 64, "git-blob-sha1": 40}
            if (
                not separator or algorithm not in lengths
                or len(digest) != lengths[algorithm]
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Checksum must be md5:<hex>, sha256:<hex>, or git-blob-sha1:<hex>")
            if algorithm == "git-blob-sha1" and self.size_bytes is None:
                raise ValueError("Git blob verification requires the exact upstream byte size")


@dataclass(frozen=True)
class GitTreeAsset:
    id: str
    repository_url: str
    commit: str
    path: str
    tree_sha1: str
    file_count: int
    size_bytes: int
    include_suffixes: tuple[str, ...] = ()

    def __post_init__(self):
        component(self.id)
        parsed = urlsplit(self.repository_url)
        if (
            parsed.scheme != "https" or parsed.hostname != "github.com"
            or parsed.username or parsed.password or not parsed.path.endswith(".git")
        ):
            raise ValueError("Git tree assets must reference a public GitHub HTTPS repository")
        if len(self.commit) != 40 or any(char not in "0123456789abcdef" for char in self.commit):
            raise ValueError("Git tree asset requires a pinned lowercase commit SHA-1")
        if len(self.tree_sha1) != 40 or any(char not in "0123456789abcdef" for char in self.tree_sha1):
            raise ValueError("Git tree asset requires an exact lowercase tree SHA-1")
        path = PurePosixPath(self.path)
        if (
            not self.path or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or "\\" in self.path
        ):
            raise ValueError("Git tree asset path must be a safe repository-relative path")
        if type(self.file_count) is not int or self.file_count < 1:
            raise ValueError("Git tree file count must be positive")
        if type(self.size_bytes) is not int or self.size_bytes < 1:
            raise ValueError("Git tree size must be positive")
        if any(
            not isinstance(suffix, str) or not suffix.startswith(".")
            or "/" in suffix or "\\" in suffix
            for suffix in self.include_suffixes
        ):
            raise ValueError("Git tree file suffix filters must be simple extensions")


def select_asset(dataset: dict, filename: str) -> Asset:
    matches = [
        entry for entry in dataset.get("selected_assets", [])
        if entry["filename"] == filename
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one catalog asset named {filename!r}")
    entry = matches[0]
    if "url" not in entry:
        raise ValueError("This asset has no verified download URL; use the source portal")
    return Asset(entry["filename"], entry["url"], entry.get("size_bytes"), entry.get("checksum"))


def select_git_tree(dataset: dict, tree_id: str) -> GitTreeAsset:
    matches = [
        entry for entry in dataset.get("selected_git_trees", [])
        if entry["id"] == tree_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one catalog Git tree named {tree_id!r}")
    entry = matches[0]
    return GitTreeAsset(
        entry["id"], entry["repository_url"], entry["commit"], entry["path"],
        entry["tree_sha1"], entry["file_count"], entry["size_bytes"],
        tuple(entry.get("include_suffixes", [])),
    )


def _git(repository: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _git_tree_manifest(repository: Path, asset: GitTreeAsset) -> list[dict]:
    tree_sha1 = _git(repository, "rev-parse", f"{asset.commit}:{asset.path}").decode().strip()
    if tree_sha1 != asset.tree_sha1:
        raise ValueError("Pinned Git tree SHA-1 mismatch")
    records = _git(
        repository, "ls-tree", "-r", "-l", "-z", asset.commit, "--", asset.path
    ).split(b"\0")
    prefix = asset.path + "/"
    files = []
    for record in records:
        if not record:
            continue
        header, encoded_path = record.split(b"\t", 1)
        mode, kind, blob_sha1, size_text = header.decode("ascii").split(" ", 3)
        path = encoded_path.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"} or not path.startswith(prefix):
            raise ValueError("Pinned Git tree contains an unsupported entry")
        relative_path = path[len(prefix):]
        pure_path = PurePosixPath(relative_path)
        if not relative_path or pure_path.is_absolute() or any(
            part in {"", ".", ".."} for part in pure_path.parts
        ):
            raise ValueError("Pinned Git tree contains an unsafe file path")
        if len(blob_sha1) != 40 or any(char not in "0123456789abcdef" for char in blob_sha1):
            raise ValueError("Pinned Git tree contains an invalid blob checksum")
        if not asset.include_suffixes or any(
            relative_path.lower().endswith(suffix.lower())
            for suffix in asset.include_suffixes
        ):
            files.append({
                "path": relative_path,
                "size_bytes": int(size_text),
                "git_blob_sha1": blob_sha1,
            })
    files.sort(key=lambda entry: entry["path"])
    if len(files) != asset.file_count or sum(entry["size_bytes"] for entry in files) != asset.size_bytes:
        raise ValueError("Pinned Git tree file inventory disagrees with catalog metadata")
    return files


def download_git_tree(
    asset: GitTreeAsset,
    dataset: dict,
    data_dir: Path,
    max_bytes: int,
    allow_local_only: bool = False,
    repository: Path = ROOT,
) -> Path:
    if max_bytes < 1:
        raise ValueError("Byte limit must be positive")
    if asset.size_bytes > max_bytes:
        raise ValueError(f"Asset set requires {asset.size_bytes} bytes, exceeding limit {max_bytes}")
    if not dataset.get("license", {}).get("spdx_id") and not allow_local_only:
        raise ValueError(
            "No verified asset license; review source terms and use --allow-local-only "
            "only after explicit local-use approval"
        )
    dataset_id = component(dataset["id"])
    data_dir = data_dir.expanduser().resolve()
    repository = repository.resolve()
    if data_dir == repository or repository in data_dir.parents:
        raise ValueError("Data directory must be outside the repository")
    parent = data_dir / dataset_id
    if parent.resolve() != parent:
        raise ValueError("Dataset directory must not redirect through a symlink")
    if parent == repository or repository in parent.parents:
        raise ValueError("Dataset directory must be outside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / (asset.id + ".download")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite {destination}")

    with tempfile.TemporaryDirectory(prefix=".git-tree-", dir=parent) as temporary:
        staging = Path(temporary)
        checkout = staging / "source"
        checkout.mkdir()
        subprocess.run(["git", "init", "--quiet", str(checkout)], check=True, capture_output=True)
        _git(checkout, "remote", "add", "origin", asset.repository_url)
        _git(
            checkout, "fetch", "--quiet", "--no-tags", "--depth=1",
            "--filter=blob:none", "origin", asset.commit,
        )
        if asset.include_suffixes:
            _git(checkout, "sparse-checkout", "init", "--no-cone")
            patterns = [f"/{asset.path}/*{suffix}" for suffix in asset.include_suffixes]
            _git(checkout, "sparse-checkout", "set", "--no-cone", *patterns)
        else:
            _git(checkout, "sparse-checkout", "init", "--cone")
            _git(checkout, "sparse-checkout", "set", asset.path)
        _git(checkout, "checkout", "--quiet", "--detach", asset.commit)
        source_files = _git_tree_manifest(checkout, asset)

        export = staging / "export"
        export.mkdir()
        frame_stream_path = export / "frames.bin"
        frame_records = []
        offset = 0
        with frame_stream_path.open("xb") as frame_stream:
            for entry in source_files:
                relative_path = entry["path"]
                source_path = checkout / asset.path / relative_path
                if source_path.is_symlink() or not source_path.is_file():
                    raise ValueError(f"Expected regular Git tree asset: {relative_path}")
                payload = source_path.read_bytes()
                if len(payload) != entry["size_bytes"] or len(payload) < 24:
                    raise ValueError(f"Git tree asset size mismatch: {relative_path}")
                if payload[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Unsupported microscopy frame format: {relative_path}")
                blob_digest = hashlib.sha1(usedforsecurity=False)
                blob_digest.update(f"blob {len(payload)}\0".encode())
                blob_digest.update(payload)
                if blob_digest.hexdigest() != entry["git_blob_sha1"]:
                    raise ValueError(f"Git blob checksum mismatch: {relative_path}")
                frame_records.append({
                    "name": Path(relative_path).name,
                    "source_path": relative_path,
                    "offset": offset,
                    "size_bytes": len(payload),
                    "width": struct.unpack(">I", payload[16:20])[0],
                    "height": struct.unpack(">I", payload[20:24])[0],
                    "git_blob_sha1": entry["git_blob_sha1"],
                    "sha256": hashlib.sha256(payload).hexdigest(),
                })
                frame_stream.write(payload)
                offset += len(payload)
                if offset > max_bytes:
                    raise ValueError("Fetched Git tree exceeds byte limit")
        if offset != asset.size_bytes or len(frame_records) != asset.file_count:
            raise ValueError("Fetched Git tree aggregate disagrees with catalog metadata")

        receipt = {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "tree_asset_id": asset.id,
            "repository_url": asset.repository_url,
            "commit": asset.commit,
            "path": asset.path,
            "tree_sha1": asset.tree_sha1,
            "file_count": len(frame_records),
            "size_bytes": offset,
            "frames_file": "frames.bin",
            "frames_sha256": hashlib.sha256(frame_stream_path.read_bytes()).hexdigest(),
            "license": dataset["license"],
            "local_only": not bool(dataset.get("license", {}).get("spdx_id")),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "frames": frame_records,
        }
        (export / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        export.replace(destination)
    return destination


def download(
    asset: Asset, dataset: dict, data_dir: Path, max_bytes: int,
    allow_unverified: bool = False, repository: Path = ROOT,
) -> Path:
    if max_bytes < 1:
        raise ValueError("Byte limit must be positive")
    dataset_id = component(dataset["id"])
    data_dir = data_dir.expanduser().resolve()
    repository = repository.resolve()
    if data_dir == repository or repository in data_dir.parents:
        raise ValueError("Data directory must be outside the repository")
    if asset.size_bytes is not None and asset.size_bytes > max_bytes:
        raise ValueError(f"Asset requires {asset.size_bytes} bytes, exceeding limit {max_bytes}")
    if asset.checksum is None and not allow_unverified:
        raise ValueError("No upstream checksum; review source terms and use --allow-unverified explicitly")

    parent = data_dir / dataset_id
    if parent.resolve() != parent:
        raise ValueError("Dataset directory must not redirect through a symlink")
    if parent == repository or repository in parent.parents:
        raise ValueError("Dataset directory must be outside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / (asset.filename + ".download")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite {destination}")

    hashes = {"sha256": hashlib.sha256()}
    if asset.checksum and asset.checksum.startswith("md5:"):
        hashes["md5"] = hashlib.md5(usedforsecurity=False)
    if asset.checksum and asset.checksum.startswith("git-blob-sha1:"):
        hashes["git-blob-sha1"] = hashlib.sha1(usedforsecurity=False)
        hashes["git-blob-sha1"].update(f"blob {asset.size_bytes}\0".encode())
    count = 0
    request = Request(asset.url, headers={"User-Agent": "neural-brains-dataset-catalog/1"})
    with tempfile.TemporaryDirectory(prefix=".download-", dir=parent) as staging:
        staged = Path(staging)
        with urlopen(request, timeout=60) as response:
            final_url = response.geturl()
            if urlsplit(final_url).scheme != "https":
                raise ValueError("Download redirected away from HTTPS")
            media_type = response.headers.get("Content-Type", "").split(";")[0].strip()
            if media_type in {"text/html", "application/xhtml+xml"}:
                raise ValueError("Server returned an HTML page instead of the selected data asset")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                raise ValueError("Server Content-Length exceeds byte limit")
            with (staged / asset.filename).open("xb") as output:
                while chunk := response.read(min(1024 * 1024, max_bytes - count + 1)):
                    count += len(chunk)
                    if count > max_bytes:
                        raise ValueError("Downloaded stream exceeds byte limit")
                    output.write(chunk)
                    for digest in hashes.values():
                        digest.update(chunk)
            if length is not None and count != int(length):
                raise ValueError("Downloaded size disagrees with server Content-Length")
        if asset.size_bytes is not None and count != asset.size_bytes:
            raise ValueError(f"Size mismatch: expected {asset.size_bytes}, received {count}")
        if asset.checksum:
            algorithm, expected = asset.checksum.split(":")
            if hashes[algorithm].hexdigest() != expected:
                raise ValueError("Upstream checksum mismatch")
        if count == 0:
            raise ValueError("Server returned an empty asset")
        receipt = {
            "dataset_id": dataset_id,
            "species": dataset["species"],
            "version": dataset.get("version"),
            "source_ids": dataset["source_ids"],
            "license": dataset["license"],
            "filename": asset.filename,
            "source_url": asset.url,
            "resolved_url": final_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": count,
            "sha256": hashes["sha256"].hexdigest(),
            "expected_size_bytes": asset.size_bytes,
            "upstream_checksum": asset.checksum,
            "upstream_checksum_verified": asset.checksum is not None,
        }
        (staged / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        destination.mkdir()
        try:
            os.link(staged / asset.filename, destination / asset.filename)
            os.link(staged / "receipt.json", destination / "receipt.json")
        except OSError:
            (destination / asset.filename).unlink(missing_ok=True)
            (destination / "receipt.json").unlink(missing_ok=True)
            destination.rmdir()
            raise
    return destination / asset.filename


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List datasets; never accesses the network")
    listing.add_argument("--species", help="Species ID from the catalog")
    plan = commands.add_parser("plan", help="Show catalog assets; never accesses the network")
    plan.add_argument("dataset")
    fetch = commands.add_parser("fetch", help="Fetch exactly one selected asset")
    fetch.add_argument("dataset")
    fetch.add_argument("--asset", required=True, help="Exact filename from plan output")
    fetch.add_argument("--data-dir", type=Path, required=True, help="Storage directory outside this repository")
    fetch.add_argument("--max-bytes", type=int, default=100_000_000, help="Hard transfer limit; default 100 MB")
    fetch.add_argument("--allow-unverified", action="store_true", help="Allow missing upstream checksum; record local SHA-256")
    fetch_tree = commands.add_parser("fetch-tree", help="Fetch one pinned GitHub subtree")
    fetch_tree.add_argument("dataset")
    fetch_tree.add_argument("--tree", required=True, help="Exact Git tree ID from plan output")
    fetch_tree.add_argument("--data-dir", type=Path, required=True)
    fetch_tree.add_argument("--max-bytes", type=int, required=True, help="Hard byte limit for the selected tree")
    fetch_tree.add_argument("--allow-local-only", action="store_true", help="Allow a user-approved local-only asset with unclear terms")
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(CATALOG.read_text())
        datasets = catalog["datasets"]
        if args.command == "list":
            if args.species and args.species not in {s["id"] for s in catalog["species"]}:
                raise ValueError(f"Unknown species ID: {args.species}")
            for dataset in datasets:
                if not args.species or dataset["species_id"] == args.species:
                    print(f"{dataset['id']}\t{dataset['species']}\t{dataset['coverage']}\t{dataset['catalog_status']}")
            return 0
        matches = [entry for entry in datasets if entry["id"] == args.dataset]
        if len(matches) != 1:
            raise ValueError(f"Unknown or duplicate dataset ID: {args.dataset}")
        dataset = matches[0]
        if args.command == "plan":
            print(json.dumps(dataset, indent=2))
            return 0
        if args.command == "fetch-tree":
            tree = select_git_tree(dataset, args.tree)
            print(f"License metadata: {json.dumps(dataset['license'])}", file=sys.stderr)
            if not dataset["license"].get("spdx_id"):
                print("WARNING: asset terms are unclear; result must remain local-only.", file=sys.stderr)
            result = download_git_tree(
                tree, dataset, args.data_dir, args.max_bytes, args.allow_local_only
            )
            print(result)
            return 0
        asset = select_asset(dataset, args.asset)
        print(f"License metadata: {json.dumps(dataset['license'])}", file=sys.stderr)
        if not dataset["license"].get("spdx_id"):
            print("WARNING: asset license is unverified; consult source terms before reuse.", file=sys.stderr)
        if asset.checksum is None:
            print("WARNING: no upstream checksum; local SHA-256 is provenance, not source verification.", file=sys.stderr)
        result = download(asset, dataset, args.data_dir, args.max_bytes, args.allow_unverified)
        print(result)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
