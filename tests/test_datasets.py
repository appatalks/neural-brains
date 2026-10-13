import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("datasets", ROOT / "scripts/datasets.py")
datasets = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = datasets
spec.loader.exec_module(datasets)


class Response(io.BytesIO):
    def __init__(self, data, length=None, media_type="application/octet-stream"):
        super().__init__(data)
        self.headers = {"Content-Type": media_type}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self):
        return "https://example.org/asset.bin"


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.repository = self.directory / "repo"
        self.repository.mkdir()
        self.storage = self.directory / "storage"
        self.payload = b"small verified connectome fixture"
        self.dataset = {
            "id": "fixture-v1", "species": "Test species", "version": "v1",
            "source_ids": ["S01"], "license": {"spdx_id": "CC-BY-4.0"},
        }
        self.asset = datasets.Asset(
            "asset.bin", "https://example.org/asset.bin", len(self.payload),
            "md5:" + hashlib.md5(self.payload, usedforsecurity=False).hexdigest(),
        )

    def fetch(self, asset=None, limit=100, allow_unverified=False):
        return datasets.download(
            asset or self.asset, self.dataset, self.storage, limit,
            allow_unverified, self.repository,
        )

    def assert_no_download(self):
        self.assertFalse(list(self.storage.rglob("asset.bin")) if self.storage.exists() else [])
        self.assertFalse(list(self.storage.rglob(".download-*")) if self.storage.exists() else [])

    def test_verified_download_and_receipt(self):
        with patch.object(datasets, "urlopen", return_value=Response(self.payload, len(self.payload))):
            result = self.fetch()
        self.assertEqual(result.read_bytes(), self.payload)
        receipt = json.loads((result.parent / "receipt.json").read_text())
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.payload).hexdigest())
        self.assertTrue(receipt["upstream_checksum_verified"])
        self.assertEqual(receipt["version"], "v1")
        self.assertEqual(receipt["source_ids"], ["S01"])
        self.assertEqual(receipt["size_bytes"], len(self.payload))

    def test_sha256_upstream_checksum(self):
        asset = datasets.Asset("asset.bin", self.asset.url, checksum="sha256:" + hashlib.sha256(self.payload).hexdigest())
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            self.assertEqual(self.fetch(asset).read_bytes(), self.payload)

    def test_git_blob_upstream_checksum(self):
        digest = hashlib.sha1(
            f"blob {len(self.payload)}\0".encode() + self.payload, usedforsecurity=False
        ).hexdigest()
        asset = datasets.Asset(
            "asset.bin", self.asset.url, len(self.payload), "git-blob-sha1:" + digest
        )
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            self.assertEqual(self.fetch(asset).read_bytes(), self.payload)
        with self.assertRaisesRegex(ValueError, "exact upstream byte size"):
            datasets.Asset("asset.bin", self.asset.url, checksum="git-blob-sha1:" + digest)

    def test_checksum_mismatch_cleans_partial_data(self):
        with patch.object(datasets, "urlopen", return_value=Response(b"x" * len(self.payload))):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                self.fetch()
        self.assert_no_download()

    def test_unknown_checksum_requires_opt_in(self):
        asset = datasets.Asset("asset.bin", self.asset.url)
        with patch.object(datasets, "urlopen") as network:
            with self.assertRaisesRegex(ValueError, "No upstream checksum"):
                self.fetch(asset)
            network.assert_not_called()
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            result = self.fetch(asset, allow_unverified=True)
        self.assertFalse(json.loads((result.parent / "receipt.json").read_text())["upstream_checksum_verified"])

    def test_catalog_size_limit_blocks_network(self):
        with patch.object(datasets, "urlopen") as network:
            with self.assertRaisesRegex(ValueError, "exceeding limit"):
                self.fetch(limit=1)
            network.assert_not_called()

    def test_unknown_length_stream_limit(self):
        asset = datasets.Asset("asset.bin", self.asset.url, checksum=self.asset.checksum)
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            with self.assertRaisesRegex(ValueError, "stream exceeds"):
                self.fetch(asset, limit=3)
        self.assert_no_download()

    def test_content_length_limit(self):
        with patch.object(datasets, "urlopen", return_value=Response(self.payload, 101)):
            with self.assertRaisesRegex(ValueError, "Content-Length exceeds"):
                self.fetch()
        self.assert_no_download()

    def test_truncated_response(self):
        with patch.object(datasets, "urlopen", return_value=Response(self.payload, 99)):
            with self.assertRaisesRegex(ValueError, "Content-Length"):
                self.fetch()
        self.assert_no_download()

    def test_catalog_size_mismatch(self):
        with patch.object(datasets, "urlopen", return_value=Response(b"short")):
            with self.assertRaisesRegex(ValueError, "Size mismatch"):
                self.fetch()
        self.assert_no_download()

    def test_html_response_rejected(self):
        with patch.object(datasets, "urlopen", return_value=Response(b"<html>login</html>", media_type="text/html")):
            with self.assertRaisesRegex(ValueError, "HTML"):
                self.fetch()
        self.assert_no_download()

    def test_existing_download_is_not_overwritten(self):
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            result = self.fetch()
        with patch.object(datasets, "urlopen") as network:
            with self.assertRaises(FileExistsError):
                self.fetch()
            network.assert_not_called()
        self.assertEqual(result.read_bytes(), self.payload)

    def test_repository_storage_rejected(self):
        for target in [self.repository, self.repository / "data"]:
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "outside the repository"):
                    datasets.download(self.asset, self.dataset, target, 100, repository=self.repository)

    def test_symlink_storage_into_repository_rejected(self):
        self.storage.symlink_to(self.repository, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            self.fetch()

    def test_dataset_folder_cannot_select_repository(self):
        self.storage = self.directory
        self.dataset["id"] = self.repository.name
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            self.fetch()

    def test_dataset_symlink_rejected(self):
        self.storage.mkdir()
        (self.storage / self.dataset["id"]).symlink_to(self.repository, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.fetch()

    def test_unsafe_asset_fields(self):
        for filename in ["../asset.bin", "..", "/asset.bin", "x\\asset.bin", "receipt.json"]:
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                datasets.Asset(filename, self.asset.url)
        for url in ["http://example.org/file", "https://user:password@example.org/file"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                datasets.Asset("asset.bin", url)
        with self.assertRaises(ValueError):
            datasets.Asset("asset.bin", self.asset.url, checksum="md5:invalid")

    def test_empty_asset_rejected(self):
        asset = datasets.Asset("asset.bin", self.asset.url)
        with patch.object(datasets, "urlopen", return_value=Response(b"")):
            with self.assertRaisesRegex(ValueError, "empty asset"):
                self.fetch(asset, allow_unverified=True)
        self.assert_no_download()

    def test_insecure_redirect_rejected(self):
        response = Response(self.payload)
        response.geturl = lambda: "http://example.org/asset.bin"
        with patch.object(datasets, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "away from HTTPS"):
                self.fetch()
        self.assert_no_download()

    def test_failed_publication_cleans_bundle(self):
        with patch.object(datasets, "urlopen", return_value=Response(self.payload)):
            with patch.object(datasets.os, "link", side_effect=OSError("publication failed")):
                with self.assertRaisesRegex(OSError, "publication failed"):
                    self.fetch()
        self.assert_no_download()
        self.assertFalse((self.storage / self.dataset["id"] / "asset.bin.download").exists())

    def test_network_failure_cleans_partial_data(self):
        error = HTTPError(self.asset.url, 503, "unavailable", {}, None)
        with patch.object(datasets, "urlopen", side_effect=error):
            with self.assertRaises(HTTPError):
                self.fetch()
        self.assert_no_download()

    def test_cli_listing_and_plan_are_offline(self):
        with patch.object(datasets, "urlopen") as network:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(datasets.main(["list", "--species", "caenorhabditis-elegans"]), 0)
            self.assertIn("wormwiring-cook2019-corrected2020", output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(datasets.main(["plan", "male-cns-v1.0"]), 0)
            self.assertEqual(json.loads(output.getvalue())["version"], "v1.0")
            network.assert_not_called()

    def test_cli_errors_are_explicit(self):
        for args in [["plan", "missing"], ["list", "--species", "missing"]]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(datasets.main(args), 1)
                self.assertIn("ERROR:", output.getvalue())

    def test_catalog_references_and_assets(self):
        catalog = json.loads(datasets.CATALOG.read_text())
        sources = {s["id"] for s in catalog["sources"]}
        species = {s["id"]: s["scientific_name"] for s in catalog["species"]}
        dataset_ids = [d["id"] for d in catalog["datasets"]]
        self.assertEqual(len(dataset_ids), len(set(dataset_ids)))
        self.assertEqual(len(sources), len(catalog["sources"]))
        self.assertEqual(len(species), len(catalog["species"]))
        self.assertTrue({"caenorhabditis-elegans", "drosophila-melanogaster", "mus-musculus"} <= species.keys())
        for source in catalog["sources"]:
            self.assertIn(source["review_status"], catalog["review_status_definitions"])
        for dataset in catalog["datasets"]:
            self.assertEqual(dataset["species"], species[dataset["species_id"]])
            self.assertTrue(set(dataset["source_ids"]) <= sources)
            for metric in dataset.get("metrics", []):
                self.assertIn(metric["source_id"], sources)
            filenames = [a["filename"] for a in dataset.get("selected_assets", [])]
            self.assertEqual(len(filenames), len(set(filenames)))
            for entry in dataset.get("selected_assets", []):
                if "url" in entry:
                    datasets.select_asset(dataset, entry["filename"])
            tree_ids = [entry["id"] for entry in dataset.get("selected_git_trees", [])]
            self.assertEqual(len(tree_ids), len(set(tree_ids)))
            for tree_id in tree_ids:
                datasets.select_git_tree(dataset, tree_id)

    def test_git_tree_selection_is_pinned_and_requires_local_only_opt_in(self):
        tree = datasets.GitTreeAsset(
            "sample-frames",
            "https://github.com/iteal/wormpose_data.git",
            "3667721534fc3062b85f165826c0ae944bceeedc",
            "datasets/sample_data",
            "f94d4ae67f0d526ec9f41c94b77b358c8d9fc8bc",
            1,
            10,
        )
        dataset = {**self.dataset, "license": {"spdx_id": None}}
        with patch.object(datasets.subprocess, "run") as network:
            with self.assertRaisesRegex(ValueError, "local-only"):
                datasets.download_git_tree(
                    tree, dataset, self.storage, 100, repository=self.repository
                )
            with self.assertRaisesRegex(ValueError, "exceeding limit"):
                datasets.download_git_tree(
                    tree, dataset, self.storage, 5, allow_local_only=True,
                    repository=self.repository,
                )
            network.assert_not_called()

    def test_git_tree_rejects_unpinned_or_unsafe_paths(self):
        arguments = [
            "sample-frames",
            "https://github.com/iteal/wormpose_data.git",
            "3667721534fc3062b85f165826c0ae944bceeedc",
            "datasets/sample_data",
            "f94d4ae67f0d526ec9f41c94b77b358c8d9fc8bc",
            1,
            10,
        ]
        for keyword, value, error in [
            ("commit", "main", "commit SHA-1"),
            ("path", "../sample_data", "safe repository-relative"),
        ]:
            updated = list(arguments)
            index = {"commit": 2, "path": 3}[keyword]
            updated[index] = value
            with self.subTest(keyword=keyword), self.assertRaisesRegex(ValueError, error):
                datasets.GitTreeAsset(*updated)


if __name__ == "__main__":
    unittest.main()
