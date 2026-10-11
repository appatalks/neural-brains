"""List, plan, and download explicitly selected catalog assets outside Git."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
        asset = select_asset(dataset, args.asset)
        print(f"License metadata: {json.dumps(dataset['license'])}", file=sys.stderr)
        if not dataset["license"].get("spdx_id"):
            print("WARNING: asset license is unverified; consult source terms before reuse.", file=sys.stderr)
        if asset.checksum is None:
            print("WARNING: no upstream checksum; local SHA-256 is provenance, not source verification.", file=sys.stderr)
        result = download(asset, dataset, args.data_dir, args.max_bytes, args.allow_unverified)
        print(result)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
