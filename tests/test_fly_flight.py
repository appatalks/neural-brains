import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
import contextlib
import io
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("flight", ROOT / "scripts/fly_flight.py")
flight = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = flight
spec.loader.exec_module(flight)


class FlightCommandTests(unittest.TestCase):
    def test_named_actions_not_magic_indices(self):
        command = flight.FlightCommand(0.5, 0.1)
        self.assertEqual(command.values(["wing_roll_right", "user_0", "wing_roll_left"]), [-0.1, 0.5, 0.1])
        with self.assertRaises(ValueError):
            command.values(["wrong"])

    def test_limits_and_reset(self):
        command = flight.FlightCommand()
        for _ in range(100):
            command.key(ord("W"))
            command.key(ord("A"))
        self.assertEqual(command.frequency, 1)
        self.assertEqual(command.differential_roll, 0.2)
        command.key(ord("X"))
        self.assertEqual(command, flight.FlightCommand())

    def test_invalid_commands_are_rejected(self):
        for value in [2, float("nan")]:
            with self.assertRaises(ValueError):
                flight.FlightCommand(value).validate()

    def test_space_and_p_share_application_pause(self):
        command = flight.FlightCommand()
        self.assertEqual(command.key(32), "P")
        self.assertEqual(command.key(ord("P")), "P")

    def test_visible_pause_status(self):
        self.assertIn("PAUSED", flight.viewer_status(True, 0, 1))
        self.assertIn("Space", flight.viewer_status(True, 0, 1))
        self.assertIn("FLYING 0.25/1.00", flight.viewer_status(False, 0.25, 1))
        self.assertIn("DONE", flight.viewer_status(False, 1, 1, finished=True))
        self.assertIn("STOPPED", flight.viewer_status(False, 0.1, 1, finished=True, failed=True))
        self.assertIn("Q", flight.viewer_status(False, 1, 1, finished=True))

    def test_trained_wing_overrides_require_opt_in(self):
        for key in "WSAD":
            self.assertFalse(flight.wing_input_allowed(ord(key), "trained", False))
            self.assertTrue(flight.wing_input_allowed(ord(key), "trained", True))
            self.assertTrue(flight.wing_input_allowed(ord(key), "diagnostic", False))
        for code in [32, ord("P"), ord("X"), 1000]:
            self.assertTrue(flight.wing_input_allowed(code, "trained", False))

    @unittest.skipUnless(importlib.util.find_spec("mujoco"), "Requires the flight MuJoCo environment")
    def test_native_reset_cannot_desynchronize_controller_state(self):
        import mujoco
        import numpy as np

        model = mujoco.MjModel.from_xml_string(
            '<mujoco><worldbody><body pos="0 0 1"><freejoint/>'
            '<geom type="sphere" size="0.05" mass="1"/></body></worldbody></mujoco>'
        )
        data = mujoco.MjData(model)
        data.qpos[2] = 3
        data.qvel[0] = 0.7
        data.time = 5
        mujoco.mj_forward(model, data)
        guard = flight.ViewerStateGuard(model, data)
        expected = guard.state.copy()
        mujoco.mj_resetData(model, data)
        with contextlib.redirect_stderr(io.StringIO()) as warnings:
            self.assertTrue(guard.restore_if_changed())
        self.assertIn("ignored a native viewer physics edit", warnings.getvalue())
        observed = np.empty_like(expected)
        mujoco.mj_getState(model, data, observed, guard.flags)
        np.testing.assert_array_equal(expected, observed)
        self.assertEqual(data.time, 5)
        self.assertEqual(data.qpos[2], 3)
        self.assertEqual(data.qvel[0], 0.7)
        self.assertFalse(guard.restore_if_changed())
        self.assertEqual(guard.rejections, 1)

    def test_verified_extraction_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "flybody-flight-imitation/fixture.zip.download"
            bundle.mkdir(parents=True)
            archive = bundle / "fixture.zip"
            with ZipFile(archive, "w") as zipped:
                zipped.writestr("sample.npy", b"fixture")
            content = archive.read_bytes()
            asset = {
                "filename": "fixture.zip", "size_bytes": len(content),
                "checksum": "md5:" + hashlib.md5(content, usedforsecurity=False).hexdigest(),
                "url": "https://example.org/archive",
            }
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"datasets": [{
                "id": "flybody-flight-imitation", "selected_assets": [asset],
                "license": {"status": "test_fixture_only"}, "source_ids": ["fixture"],
            }]}))
            (bundle / "receipt.json").write_text(json.dumps({
                "sha256": hashlib.sha256(content).hexdigest(), "source_url": asset["url"],
                "upstream_checksum": asset["checksum"], "dataset_id": "flybody-flight-imitation",
            }))
            with patch.object(flight, "CATALOG", catalog), patch.object(flight, "MEMBERS", {"sample.npy": 7}):
                paths = flight.prepare_data(root)
                self.assertEqual(paths["sample.npy"].read_bytes(), b"fixture")
                self.assertEqual(flight.prepare_data(root), paths)
                paths["sample.npy"].write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Previously extracted data changed"):
                    flight.prepare_data(root)

    def test_extraction_rejects_unexpected_archive_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "flybody-flight-imitation/fixture.zip.download"
            bundle.mkdir(parents=True)
            archive = bundle / "fixture.zip"
            with ZipFile(archive, "w") as zipped:
                zipped.writestr("../escape", b"bad")
            content = archive.read_bytes()
            asset = {
                "filename": "fixture.zip", "size_bytes": len(content),
                "checksum": "md5:" + hashlib.md5(content, usedforsecurity=False).hexdigest(),
                "url": "https://example.org/archive",
            }
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"datasets": [{
                "id": "flybody-flight-imitation", "selected_assets": [asset],
                "license": {}, "source_ids": [],
            }]}))
            (bundle / "receipt.json").write_text(json.dumps({
                "sha256": hashlib.sha256(content).hexdigest(), "source_url": asset["url"],
                "upstream_checksum": asset["checksum"], "dataset_id": "flybody-flight-imitation",
            }))
            with patch.object(flight, "CATALOG", catalog):
                with self.assertRaisesRegex(ValueError, "archive members differ"):
                    flight.prepare_data(root)
            self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
