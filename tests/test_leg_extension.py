import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_leg_extension import DNP10_IDS, LegExtension, verified_dnp10
from fly_feeding import BrainClient
from fly_unified import MotorAdapter


def metadata():
    return {"sensorimotor_candidates": [
        {"population": "DNp10", "side": side, "root_id": value, "in_model": True,
         "ambiguous_type_correspondence": False} for side, value in DNP10_IDS.items()]}


def response(count, sequence=1):
    return {"sensorimotor_spikes": {value: count if side == "left" else 0
                                  for side, value in DNP10_IDS.items()},
            "neuron_activity": {"episode": 0, "sequence": sequence,
                                "start_ms": (sequence-1)*10., "end_ms": sequence*10.}}


class LegExtensionTests(unittest.TestCase):
    def test_exact_identity_and_namespace(self):
        self.assertEqual(verified_dnp10(metadata()), list(DNP10_IDS.values()))
        for changes in ({}, {"root_id": "10835"}, {"in_model": False},
                        {"ambiguous_type_correspondence": True}, {"side": "right"}):
            raw = metadata()
            if not changes:
                raw["sensorimotor_candidates"].pop()
            else:
                raw["sensorimotor_candidates"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                verified_dnp10(raw)

    def test_real_counts_only_saturating_and_decaying(self):
        decoder = LegExtension(metadata())
        self.assertEqual(decoder.advance(.01, True), 0)
        decoder.accept(response(1))
        expected = 1-math.exp(-.35)
        self.assertAlmostEqual(decoder.activation, expected)
        self.assertEqual(decoder.advance(.01, False), 0)
        self.assertGreater(decoder.activation, 0)
        decoder.accept(response(100, 2))
        self.assertLessEqual(decoder.activation, 1)
        self.assertLess(decoder.advance(1, True), .00001)
        decoder.reset()
        self.assertEqual(decoder.total_spikes, 0)
        self.assertEqual(decoder.activation, 0)
        decoder.accept(response(0))
        self.assertEqual(decoder.activation, 0)

    def test_duplicate_missing_invalid_and_cross_episode_intervals_fail(self):
        for edit in ("duplicate", "gap", "episode", "counts"):
            decoder = LegExtension(metadata())
            decoder.accept(response(1))
            reply = response(0, 2)
            if edit == "duplicate":
                reply = response(0)
            elif edit == "gap":
                reply["neuron_activity"]["start_ms"] = 11.
            elif edit == "episode":
                reply["neuron_activity"]["episode"] = 1
            else:
                reply["sensorimotor_spikes"][DNP10_IDS["left"]] = True
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                decoder.accept(reply)
        for dt, flying in [(0, True), (float("nan"), True), (.01, 1)]:
            with self.assertRaises(ValueError):
                decoder.advance(dt, flying)

    def test_only_named_tibia_actuators_change_and_baseline_is_exact(self):
        import numpy as np

        names = ["wing"] + [f"tibia_T{leg}_{side}" for side in ("right", "left") for leg in (3, 2, 1)]
        adapter = SimpleNamespace(np=np, spec=SimpleNamespace(
            name="\t".join(names), minimum=np.full(7, -1.35), maximum=np.full(7, 1.3)))
        baseline = np.zeros(7)
        self.assertTrue(np.array_equal(MotorAdapter.leg_extension_action(adapter, baseline, 0), baseline))
        action = MotorAdapter.leg_extension_action(adapter, baseline, .5)
        self.assertEqual(action[0], 0)
        self.assertTrue(np.allclose(action[1:], .45))
        self.assertTrue(np.array_equal(baseline, np.zeros(7)))
        for activation in (-1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                MotorAdapter.leg_extension_action(adapter, baseline, activation)

    def test_research_intervention_requires_full_contract(self):
        for options in ({}, {"takeoff": True}, {"telemetry": True},
                        {"takeoff": True, "telemetry": True, "dnp10_intervention": "invalid"}):
            with self.assertRaises(ValueError):
                BrainClient(Path("/unused"), Path("/unused"), Path("/unused"), 420,
                            **{"dnp10_intervention": "silence", **options})

    def test_silent_held_out_response_fails_without_crashing_or_counting_hidden_geometry(self):
        from test_leg_extension_causality import CASES, PROTOCOLS, evaluate

        results, traces = {}, {}
        for protocol in PROTOCOLS:
            for case in CASES:
                key = (protocol["name"], case)
                results[key] = {
                    "dn_spikes": 0, "first_motor_s": None, "first_dn_delivery_s": None,
                    "neural_sha256": "silent", "physical_sha256": "baseline",
                    "peak_activation": 0., "final_activation": 0., "network_spikes": 0,
                    "front_tibia_absolute_force_integral": [0., 0.],
                    "floor_contact_steps": 0, "sphere_contact_steps": 0,
                    "minimum_upright_cosine": .8,
                }
                traces[key] = [
                    {"front_tibia_rad": [0., 0.], "front_tip_forward_mm": [0., 0.],
                     "end_s": .01, "feedback_probe": False,
                     "response": {"network_spikes": 0}, "stimulus": False,
                     "looming": [{"angular_size_rad": .3 if case == "intact" else .2,
                                               "visible": False}]}]
        checks = evaluate(results, traces)
        for protocol in PROTOCOLS:
            name = protocol["name"]
            self.assertFalse(checks[f"{name}:intact-response"])
            self.assertFalse(checks[f"{name}:no-retrocausal-actuation"])
            self.assertFalse(checks[f"{name}:physics-to-sensory-feedback"])
            self.assertEqual(results[(name, "intact")]["sensory_feedback_angular_difference_rad"], 0)
        self.assertFalse(all(checks.values()))
