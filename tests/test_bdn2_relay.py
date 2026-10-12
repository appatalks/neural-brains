import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from bdn2_relay import CountRelay, DECAY_S, MODEL_CURRENT_PER_SPIKE
from export_bdn2_packets import BDN2_IDS, walking_ids, matched_events
from test_brain_joint_relay import integrate_packets
from test_bdn2_vnc import parameters


def packet(sequence, count, episode=1):
    return {"brain_time_ms": sequence*10, "sensorimotor_spikes": {
        BDN2_IDS["left"]: count, BDN2_IDS["right"]: 0},
        "neuron_activity": {"sequence": sequence, "episode": episode,
                            "start_ms": (sequence-1)*10, "end_ms": sequence*10}}


class SpikeRelayTests(unittest.TestCase):
    def test_research_parameters_are_explicit_and_default_is_preserved(self):
        relay = CountRelay(current_per_spike=125., decay_s=.08)
        relay.accept(packet(1, 1))
        relay.accept(packet(2, 0))
        self.assertAlmostEqual(relay.current, 125*math.exp(-.01/.08))
        for kwargs in ({"current_per_spike": 0}, {"decay_s": -1}, {"decay_s": math.nan},
                       {"current_per_spike": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                CountRelay(**kwargs)

    def test_boundary_delivery_decay_and_disconnected_observation(self):
        relay = CountRelay()
        self.assertEqual(relay.current, 0.)
        relay.validate(packet(1, 2))
        self.assertEqual(relay.current, 0.)
        delivered = relay.accept(packet(1, 2))
        self.assertEqual(delivered["delivery_ms"], 10.)
        self.assertEqual(delivered["source_count"], 2)
        self.assertEqual(relay.current, 2*MODEL_CURRENT_PER_SPIKE)
        relay.accept(packet(2, 0))
        self.assertAlmostEqual(relay.current, 2*MODEL_CURRENT_PER_SPIKE*math.exp(-.01/DECAY_S))
        disconnected = CountRelay(False)
        row = disconnected.accept(packet(1, 2))
        self.assertEqual(row["source_count"], 2)
        self.assertEqual(row["delivered_count"], 0)
        self.assertEqual(disconnected.current, 0.)

    def test_stale_gapped_episode_bad_count_and_clock_are_rejected_without_state_change(self):
        for case in ("stale", "gap", "episode", "count", "boolean", "time", "cadence", "missing"):
            relay = CountRelay()
            relay.accept(packet(1, 1))
            before = relay.current
            candidate = packet(2, 1)
            if case == "stale":
                candidate = packet(1, 1)
            elif case == "gap":
                candidate = packet(3, 1)
            elif case == "episode":
                candidate = packet(2, 1, 2)
            elif case == "count":
                candidate["sensorimotor_spikes"][BDN2_IDS["left"]] = -1
            elif case == "boolean":
                candidate["sensorimotor_spikes"][BDN2_IDS["left"]] = True
            elif case == "time":
                candidate["brain_time_ms"] = 19
            elif case == "cadence":
                candidate["neuron_activity"]["end_ms"] = 21
            else:
                candidate.pop("neuron_activity")
            with self.subTest(case=case), self.assertRaises(ValueError):
                relay.accept(candidate)
            self.assertEqual(relay.current, before)
            self.assertEqual(relay.sequence, 1)

    def test_source_identities_are_exact_and_model_verified(self):
        rows = []
        for side, value in BDN2_IDS.items():
            rows.append({"population": "BDN2", "side": side, "root_id": value,
                         "in_model": True, "ambiguous_type_correspondence": False})
        for name, count in (("BPN", 12), ("FG", 2)):
            start = 1000+len(rows)
            rows.extend({"population": name, "root_id": str(start+index),
                         "in_model": True, "ambiguous_type_correspondence": False}
                        for index in range(count))
        metadata = {"sensorimotor_candidates": rows}
        self.assertEqual(walking_ids(metadata)["BDN2"], list(BDN2_IDS.values()))
        bad = copy.deepcopy(metadata)
        bad["sensorimotor_candidates"][0]["side"] = "right"
        with self.assertRaises(ValueError):
            walking_ids(bad)


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Existing numerical environment required")
class PacketIntegrationTests(unittest.TestCase):
    def test_matched_external_events_are_identical_for_the_FG_causal_pair(self):
        import numpy as np
        channels, ticks = matched_events(431, "fg-coactivation")
        cut_channels, cut_ticks = matched_events(431, "fg-output-cut")
        np.testing.assert_array_equal(channels, cut_channels)
        np.testing.assert_array_equal(ticks, cut_ticks)
        bpn_channels, bpn_ticks = matched_events(431, "intact")
        np.testing.assert_array_equal(bpn_channels, channels[channels < 12])
        np.testing.assert_array_equal(bpn_ticks, ticks[channels < 12])
        self.assertTrue((ticks[channels < 12] >= 500).all())
        self.assertTrue((ticks[channels < 12] < 8000).all())
        self.assertTrue((ticks[channels >= 12] >= 3000).all())
        self.assertTrue((ticks[channels >= 12] < 5000).all())
        self.assertEqual(len(matched_events(431, "no-input")[0]), 0)

    def fixture(self):
        import numpy as np
        weights = np.zeros((5, 5))
        weights[0, 4] = 100.
        responses = [packet(index+1, 1 if index == 9 else 0) for index in range(100)]
        return weights, parameters(np.ones(5)), responses

    def test_no_response_before_packet_delivery_and_exact_replay(self):
        import numpy as np
        weights, params, responses = self.fixture()
        times, rates, deliveries = integrate_packets(weights, params, 4, responses)
        self.assertEqual(deliveries[9]["delivery_ms"], 100)
        np.testing.assert_array_equal(rates[:, times <= .1], np.zeros_like(rates[:, times <= .1]))
        self.assertGreater(rates[4].max(), 0)
        _, replay, _ = integrate_packets(weights, params, 4, responses)
        np.testing.assert_array_equal(rates, replay)

    def test_disconnection_and_output_silencing_preserve_observed_packets(self):
        import numpy as np
        weights, params, responses = self.fixture()
        original = copy.deepcopy(responses)
        _, cut, deliveries = integrate_packets(weights, params, 4, responses, connected=False)
        np.testing.assert_array_equal(cut, np.zeros_like(cut))
        self.assertEqual(deliveries[9]["source_count"], 1)
        _, silence, _ = integrate_packets(weights, params, 4, responses, silence_motor=True)
        self.assertGreater(silence[0].max(), 0)
        np.testing.assert_array_equal(silence[4], np.zeros(1001))
        self.assertEqual(responses, original)

    def test_missing_or_stale_packets_do_not_get_filled_with_synthetic_activity(self):
        weights, params, responses = self.fixture()
        with self.assertRaises(ValueError):
            integrate_packets(weights, params, 4, responses[:-1])
        responses[10] = responses[9]
        with self.assertRaises(ValueError):
            integrate_packets(weights, params, 4, responses)
