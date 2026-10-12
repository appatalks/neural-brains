import json
import math
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_looming import GRADED_ENCODER, SphereLooming, graded_visual_rates, validate_visual_rates
from fly_feeding import BrainClient
from datasets import ROOT


def sample(angle=.1, velocity=.1, visible=True):
    return {"angular_size_rad": angle, "angular_velocity_rad_s": velocity, "visible": visible}


class GradedVisionTests(unittest.TestCase):
    def test_declared_rates_and_feature_separation(self):
        rates = graded_visual_rates([sample()])
        self.assertAlmostEqual(rates["LC4"], 50.)
        self.assertAlmostEqual(rates["LPLC2"], 100 * (2/3)**2)
        larger = graded_visual_rates([sample(angle=.2)])
        self.assertEqual(larger["LC4"], rates["LC4"])
        self.assertGreater(larger["LPLC2"], rates["LPLC2"])
        faster = graded_visual_rates([sample(velocity=.2)])
        self.assertGreater(faster["LC4"], rates["LC4"])
        self.assertGreater(faster["LPLC2"], rates["LPLC2"])

    def test_continuity_below_old_binary_thresholds_and_no_double_counted_eyes(self):
        below = graded_visual_rates([sample(.0999, .04)])
        above = graded_visual_rates([sample(.1001, .04)])
        self.assertGreater(below["LC4"], 0)
        self.assertLess(abs(below["LPLC2"]-above["LPLC2"]), .1)
        self.assertEqual(graded_visual_rates([sample(), sample()]), graded_visual_rates([sample()]))
        changed = graded_visual_rates([sample(.1+1e-7, .1+1e-7)])
        self.assertNotEqual(changed, graded_visual_rates([sample()]))
        self.assertLess(max(graded_visual_rates([sample(math.pi, 1e100)]).values()), 101)

    def test_disabled_occluded_static_receding_and_visibility_restart(self):
        for feature in [sample(visible=False), sample(velocity=0), sample(velocity=-1)]:
            self.assertEqual(graded_visual_rates([feature]), {"LC4": 0., "LPLC2": 0.})
        state = SphereLooming()
        self.assertEqual(graded_visual_rates([state.sample(10, 1, .01, True)]),
                         {"LC4": 0., "LPLC2": 0.})
        self.assertGreater(graded_visual_rates([state.sample(9, 1, .01, True)])["LC4"], 0)
        state.sample(8, 1, .01, True, False)
        self.assertEqual(graded_visual_rates([state.sample(7, 1, .01, True)]),
                         {"LC4": 0., "LPLC2": 0.})

    def test_exact_rate_schema_and_invalid_geometry(self):
        for rates in [None, {}, {"LC4": 1}, {"LC4": 1, "LPLC2": 1, "GF": 1},
                      {"LC4": True, "LPLC2": 1}, {"LC4": math.nan, "LPLC2": 1},
                      {"LC4": -1, "LPLC2": 1}, {"LC4": 101, "LPLC2": 1}]:
            with self.subTest(rates=rates), self.assertRaises(ValueError):
                validate_visual_rates(rates)
        for changes in ({"visible": 1}, {"angular_size_rad": math.inf},
                        {"angular_size_rad": -1}, {"angular_velocity_rad_s": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                graded_visual_rates([{**sample(), **changes}])
        with self.assertRaises(ValueError):
            graded_visual_rates([])
        self.assertIn("Not fitted", GRADED_ENCODER["scope"])

    def test_client_requires_opt_in_and_copies_rate_request(self):
        client = BrainClient.__new__(BrainClient)
        client.pending = False
        client.graded_vision = True
        client.walking_control = False
        client.send = Mock()
        rates = {"LC4": 10, "LPLC2": 20}
        client.begin_step(10, False, True, rates)
        rates["LC4"] = 99
        self.assertEqual(client.expected_interval[-1]["LC4"], 10)
        self.assertEqual(client.send.call_args.args[0]["visual_rates_Hz"], {"LC4": 10., "LPLC2": 20.})
        with self.assertRaises(RuntimeError):
            client.begin_step(10, False, True, rates)
        client.pending = False
        for looming, rates in [(False, {"LC4": 1, "LPLC2": 1}), (True, {"LC4": 0, "LPLC2": 0}),
                               (False, None)]:
            with self.subTest(looming=looming), self.assertRaises(ValueError):
                client.begin_step(10, False, looming, rates)
        client.graded_vision = False
        with self.assertRaises(ValueError):
            client.begin_step(10, False, True, {"LC4": 100, "LPLC2": 100})
        client.begin_step(10, False, True)
        self.assertNotIn("visual_rates_Hz", client.send.call_args.args[0])

    def test_client_checks_exact_applied_rates_before_advancing_activity(self):
        client = BrainClient.__new__(BrainClient)
        client.pending = True
        client.graded_vision = True
        client.walking_control = False
        client.activity_reader = Mock()
        client.expected_interval = (10., False, True, {"LC4": 10., "LPLC2": 20.})
        reply = {"duration_ms": 10., "sugar_contact": False, "looming_active": True,
                 "visual_rates_Hz": {"LC4": 11., "LPLC2": 20.}}
        client.receive = Mock(return_value=reply)
        with self.assertRaisesRegex(RuntimeError, "graded input rates"):
            client.finish_step()
        client.activity_reader.accept.assert_not_called()
        self.assertTrue(client.pending)

    def test_causal_assay_rejects_source_drift(self):
        import hashlib
        from unittest.mock import patch
        from test_graded_visual_feedback import verify_sources

        digest = hashlib.sha256(b"original").hexdigest()
        with patch("pathlib.Path.read_bytes", return_value=b"original"):
            verify_sources({"fly_looming.py": digest})
        with patch("pathlib.Path.read_bytes", return_value=b"edited"):
            with self.assertRaisesRegex(RuntimeError, "Source files changed"):
                verify_sources({"fly_looming.py": digest})

    def test_sphere_histories_reset_and_prune_when_sources_are_removed(self):
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import patch
        from fly_looming import SphereVision

        vision = SphereVision()
        model = SimpleNamespace(ngeom=2, geom_type=np.full(2, 2), geom_size=np.ones((2, 3)))
        data = SimpleNamespace(geom_xpos=np.zeros((2, 3)))
        source = {"geom_id": 0, "name": "saved_sphere", "enabled": True}
        distance = [10.]
        def views(*args):
            return [{"camera_id": eye, "distance_mm": distance[0], "visible": True,
                     "occluded": False} for eye in (1, 2)]
        with patch("fly_looming.finger_visibility", side_effect=views):
            first = vision.sample(model, data, [source], [1, 2], 0, .01)
            self.assertEqual(graded_visual_rates(first), {"LC4": 0., "LPLC2": 0.})
            distance[0] = 9.
            self.assertGreater(graded_visual_rates(vision.sample(model, data, [source], [1, 2], 0, .01))["LC4"], 0)
            self.assertEqual(len(vision.states), 2)
            vision.forget(0)
            self.assertEqual(len(vision.states), 0)
            self.assertEqual(graded_visual_rates(vision.sample(model, data, [source], [1, 2], 0, .01)),
                             {"LC4": 0., "LPLC2": 0.})
            vision.sample(model, data, [], [1, 2], 0, .01)
            self.assertEqual(len(vision.states), 0)
            self.assertEqual(graded_visual_rates(vision.sample(model, data, [source], [1, 2], 0, .01)),
                             {"LC4": 0., "LPLC2": 0.})
            vision.reset()
            self.assertFalse(vision.states)
            with self.assertRaises(ValueError):
                vision.sample(model, data, [source, source], [1, 2], 0, .01)
            model.geom_type[0] = 6
            with self.assertRaises(ValueError):
                vision.sample(model, data, [source], [1, 2], 0, .01)


@unittest.skipUnless(os.environ.get("FLY_GRADED_DATA_DIR") and os.environ.get("FLY_GRADED_OUTPUT_DIR"),
                     "Set explicit external data/output directories for actual graded-network parity")
class ActualGradedVisionTests(unittest.TestCase):
    def test_binary_maximum_parity_silence_reset_and_population_specific_drive(self):
        from fly_walking import external_output

        output = external_output(Path(os.environ["FLY_GRADED_OUTPUT_DIR"]))
        output.mkdir(parents=True)
        replies = {}
        for graded in (False, True):
            directory = output/("graded" if graded else "binary")
            directory.mkdir()
            brain = BrainClient(ROOT/".venv/bin/python", Path(os.environ["FLY_GRADED_DATA_DIR"]),
                                directory, 420, takeoff=True, telemetry=True, graded_vision=graded)
            try:
                (directory/"metadata.json").write_text(json.dumps(brain.metadata)+"\n")
                full = {"LC4": 100., "LPLC2": 100.} if graded else None
                brain.begin_step(1000, False, True, full)
                first = brain.finish_step()
                (directory/"response.json").write_text(json.dumps(first)+"\n")
                replies[graded] = {k: v for k,v in first.items() if k != "visual_rates_Hz"}
                brain.reset()
                brain.begin_step(1000, False, True, full)
                replay = brain.finish_step()
                self.assertEqual(first["neuron_activity"]["indices"], replay["neuron_activity"]["indices"])
                self.assertEqual(first["neuron_activity"]["counts"], replay["neuron_activity"]["counts"])
                brain.reset()
                brain.begin_step(1000, False, False, {"LC4": 0., "LPLC2": 0.} if graded else None)
                self.assertEqual(brain.finish_step()["network_spikes"], 0)
                if graded:
                    ids = brain.metadata["neuron_ids"]
                    groups = brain.metadata["visual_population_ids"]
                    self.assertEqual(set(groups["LC4"]) | set(groups["LPLC2"]),
                                     set(brain.metadata["visual_input_ids"]))
                    self.assertFalse(set(groups["LC4"]) & set(groups["LPLC2"]))
                    probes = []
                    for population in ("LC4", "LPLC2"):
                        brain.reset()
                        rates = {p: 100. if p == population else 0. for p in groups}
                        brain.begin_step(100, False, True, rates)
                        reply = brain.finish_step()
                        probes.append(reply)
                        packet = reply["neuron_activity"]
                        fired = {ids[i]: count for i,count in zip(packet["indices"], packet["counts"])}
                        self.assertGreater(sum(fired.get(value, 0) for value in groups[population]), 0)
                        self.assertEqual(reply["visual_rates_Hz"], rates)
                    (directory/"population-probes.json").write_text(json.dumps(probes)+"\n")
            finally:
                brain.close()
        self.assertEqual(replies[False], replies[True])
        self.assertEqual(replies[True]["network_spikes"], 58750)
        (output/"status.json").write_text('{"status":"passed"}\n')
