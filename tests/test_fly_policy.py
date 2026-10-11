import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fly_policy


class FlightPolicyTests(unittest.TestCase):
    def record(self, position=0.05, angle=10, contacts=0):
        return {"position_error_cm": position, "orientation_error_deg": angle, "floor_contacts": contacts}

    def test_tracking_passes_predefined_limits(self):
        result = fly_policy.evaluate_tracking([self.record()], 0.5, 0.5)
        self.assertTrue(result["passed"])
        self.assertEqual(result["thresholds"]["rms_position_error_cm"], 0.1)

    def test_each_tracking_limit_fails_independently(self):
        for record in [self.record(position=0.11), self.record(angle=46), self.record(contacts=1)]:
            with self.subTest(record=record):
                self.assertFalse(fly_policy.evaluate_tracking([record], 0.5, 0.5)["passed"])
        self.assertFalse(fly_policy.evaluate_tracking([self.record()], 0.05, 0.5)["passed"])

    def test_invalid_observations_and_durations(self):
        for record in [self.record(position=math.nan), self.record(angle=-1), self.record(contacts=-1)]:
            with self.subTest(record=record), self.assertRaises(ValueError):
                fly_policy.evaluate_tracking([record], 0.5, 0.5)
        with self.assertRaises(ValueError):
            fly_policy.evaluate_tracking([], 0.5, 0.5)
        with self.assertRaises(ValueError):
            fly_policy.evaluate_tracking([self.record()], 0.5, math.nan)

    def test_quaternion_error_is_sign_invariant(self):
        for quat in [[1, 0, 0, 0], [-1, 0, 0, 0]]:
            distance, angle = fly_policy.tracking_errors({
                "walker/ref_displacement": [[0.3, 0.4, 0]],
                "walker/ref_root_quat": [quat],
            })
            self.assertAlmostEqual(distance, 0.5)
            self.assertEqual(angle, 0)

    def test_invalid_quaternions(self):
        for quat in [[0, 0, 0, 0], [1, 0], [math.nan, 0, 0, 0]]:
            with self.subTest(quat=quat), self.assertRaises(ValueError):
                fly_policy.tracking_errors({
                    "walker/ref_displacement": [[0, 0, 0]],
                    "walker/ref_root_quat": [quat],
                })

    def test_policy_extraction_and_tamper_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "flybody-flight-imitation/trained-fly-policies.zip.download"
            bundle.mkdir(parents=True)
            archive = bundle / "trained-fly-policies.zip"
            with ZipFile(archive, "w") as zipped:
                zipped.writestr("flight/saved_model.pb", b"fixture")
                zipped.writestr("walking/unused.pb", b"not extracted")
            content = archive.read_bytes()
            checksum = "md5:" + hashlib.md5(content, usedforsecurity=False).hexdigest()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"datasets": [{
                "id": "flybody-flight-imitation", "source_ids": [], "license": {},
                "selected_assets": [{
                    "filename": archive.name, "size_bytes": len(content), "checksum": checksum,
                    "url": "https://example.org/policy",
                }],
            }]}))
            receipt = {
                "dataset_id": "flybody-flight-imitation", "upstream_checksum": checksum,
                "sha256": hashlib.sha256(content).hexdigest(), "source_url": "https://example.org/policy",
            }
            (bundle / "receipt.json").write_text(json.dumps(receipt))
            with patch.object(fly_policy, "POLICY_MEMBERS", {"flight/saved_model.pb": 7}):
                path = fly_policy.prepare_policy(root, catalog)
                self.assertEqual((path / "saved_model.pb").read_bytes(), b"fixture")
                self.assertFalse((path.parent / "walking").exists())
                self.assertEqual(fly_policy.prepare_policy(root, catalog), path)
                (path / "saved_model.pb").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Previously extracted policy changed"):
                    fly_policy.prepare_policy(root, catalog)

    def test_only_verified_policy_families_allowed(self):
        with self.assertRaisesRegex(ValueError, "verified"):
            fly_policy.prepare_policy(Path("/unused"), Path("/unused"), "unknown")

    def test_benchmark_has_independent_phases_and_perturbation(self):
        cases = json.loads((ROOT / "experiments/fly-flight/benchmark.json").read_text())["cases"]
        seeds = {case["seed"] for case in cases if case["trajectory"] == 48 and case["gust_uN"] == 0}
        self.assertEqual(seeds, {0, 1, 2, 3, 4})
        self.assertTrue(any(case["gust_uN"] == 2 for case in cases))
        self.assertGreaterEqual(len({case["trajectory"] for case in cases}), 4)


if __name__ == "__main__":
    unittest.main()
