import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("flywire_sugar", ROOT / "scripts/run_flywire_sugar.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FlywireSugarTests(unittest.TestCase):
    def test_provider_md5_and_sha256_inputs_are_revalidated(self):
        payload = b"primary supplement fixture"
        for algorithm in ("md5", "sha256"):
            checksum = algorithm+":"+hashlib.new(algorithm, payload, usedforsecurity=False).hexdigest()
            dataset = {"id": "fixture", "selected_assets": [
                {"filename": "table.xlsx", "url": "https://example.org/table.xlsx",
                 "size_bytes": len(payload), "checksum": checksum},
            ]}
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                bundle = root/"fixture/table.xlsx.download"
                bundle.mkdir(parents=True)
                path = bundle/"table.xlsx"
                path.write_bytes(payload)
                (bundle/"receipt.json").write_text(json.dumps({
                    "sha256": hashlib.sha256(payload).hexdigest(), "upstream_checksum": checksum,
                    "dataset_id": "fixture", "source_url": "https://example.org/table.xlsx",
                }))
                self.assertEqual(runner.verified_inputs(root, dataset), {"table.xlsx": path})
                path.write_bytes(b"corrupt")
                with self.assertRaisesRegex(ValueError, "verification failed"):
                    runner.verified_inputs(root, dataset)

    def test_full_activation_passes(self):
        result = runner.acceptance([5] * 30, 0, 30)
        self.assertTrue(result["passed"])
        self.assertEqual(result["mn9_activation_fraction"], 1)

    def test_missing_activation_fails(self):
        result = runner.acceptance([5] * 29 + [0], 0, 30)
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "failed")

    def test_control_activity_fails(self):
        self.assertFalse(runner.acceptance([5] * 30, 1, 30)["passed"])

    def test_smoke_is_not_reproduction(self):
        result = runner.acceptance([5], 0, 30)
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "incomplete_smoke_test")

    def test_invalid_observations_rejected(self):
        for counts in [[], [-1]]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                runner.acceptance(counts, 0, 30)

    def test_protocol_and_snapshot(self):
        protocol = json.loads(runner.PROTOCOL.read_text())
        catalog = json.loads(runner.CATALOG.read_text())
        dataset = next(d for d in catalog["datasets"] if d["id"] == protocol["dataset_id"])
        self.assertEqual(protocol["trial_count"], 30)
        self.assertEqual(protocol["stimulation_Hz"], 100)
        self.assertEqual(len(set(protocol["input_ids"])), 21)
        self.assertNotIn(protocol["readout_id"], protocol["input_ids"])
        for asset in dataset["selected_assets"]:
            self.assertIn(protocol["upstream_commit"], asset["url"])
            self.assertTrue(asset["checksum"].startswith("git-blob-sha1:"))

    def test_inputs_and_receipts_revalidated(self):
        payload = b"pinned source fixture"
        digest = hashlib.sha1(
            f"blob {len(payload)}\0".encode() + payload, usedforsecurity=False
        ).hexdigest()
        checksum = "git-blob-sha1:" + digest
        dataset = {
            "id": "fixture",
            "selected_assets": [{
                "filename": "model.py", "url": "https://example.org/model.py",
                "size_bytes": len(payload), "checksum": checksum,
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "fixture/model.py.download"
            bundle.mkdir(parents=True)
            path = bundle / "model.py"
            path.write_bytes(payload)
            receipt = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "upstream_checksum": checksum, "dataset_id": "fixture",
                "source_url": "https://example.org/model.py",
            }
            receipt_path = bundle / "receipt.json"
            receipt_path.write_text(json.dumps(receipt))
            self.assertEqual(runner.verified_inputs(root, dataset), {"model.py": path})
            receipt["sha256"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                runner.verified_inputs(root, dataset)
            path.write_bytes(b"corrupted payload")
            with self.assertRaisesRegex(ValueError, "Git blob verification failed"):
                runner.verified_inputs(root, dataset)


if __name__ == "__main__":
    unittest.main()
