import copy
import json
import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_activity import ActivityReader, activity_packet


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "neurons": 4, "neuron_ids": ["720575940660219265", "2", "3", "4"],
            "mn9_id": "720575940660219265", "gf_ids": ["3"],
        }
        self.reader = ActivityReader(self.metadata)
        self.response = {
            "brain_time_ms": 10, "duration_ms": 10,
            "network_spikes": 6, "mn9_spikes": 2, "giant_fiber_spikes": {"3": 1},
            "neuron_activity": activity_packet([2, 0, 1, 3], 0, 1, 0, 10),
        }

    def test_exact_sparse_counts_and_string_ids(self):
        self.assertEqual(self.reader.accept(self.response)["indices"], [0, 2, 3])
        self.assertEqual(self.reader.ids[0], "720575940660219265")
        self.assertEqual(self.reader.sequence, 1)

    def test_stale_packets_and_invalid_counts_rejected_without_advancing(self):
        for field, value in [
            ("schema_version", True), ("sequence", 0), ("episode", 1),
            ("indices", [0, 0, 3]), ("indices", [0, 2, 4]),
            ("counts", [2, 0, 4]), ("counts", [True, 1, 4]),
            ("network_spikes", 7), ("end_ms", float("nan")), ("start_ms", 1),
        ]:
            with self.subTest(field=field):
                response = copy.deepcopy(self.response)
                response["neuron_activity"][field] = value
                with self.assertRaises(ValueError):
                    self.reader.accept(response)
                self.assertEqual(self.reader.sequence, 0)
        self.reader.accept(self.response)
        with self.assertRaises(ValueError):
            self.reader.accept(self.response)

    def test_readout_and_interval_mismatches_rejected(self):
        for field, value in [
            ("mn9_spikes", 1), ("giant_fiber_spikes", {"3": 0}),
            ("network_spikes", 7), ("duration_ms", 9), ("brain_time_ms", 9),
        ]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.reader.accept({**self.response, field: value})

    def test_empty_interval_and_reset(self):
        self.reader.accept(self.response)
        reset = {"op": "reset", "brain_time_ms": 0, "neuron_activity": activity_packet([], 1, 0, 0, 0)}
        with self.assertRaises(ValueError):
            self.reader.accept({**reset, "brain_time_ms": 10}, reset=True)
        self.reader.accept(reset, reset=True)
        silent = {
            "brain_time_ms": 10, "duration_ms": 10, "network_spikes": 0,
            "mn9_spikes": 0, "giant_fiber_spikes": {"3": 0},
            "neuron_activity": activity_packet([0, 0, 0, 0], 1, 1, 0, 10),
        }
        self.reader.accept(silent)
        self.assertEqual(self.reader.episode, 1)
        self.assertEqual(self.reader.sequence, 1)

    def test_metadata_rejects_duplicate_and_nonstring_ids(self):
        for ids in [["1", "1", "3", "4"], [1, "2", "3", "4"], ["١", "2", "3", "4"]]:
            with self.assertRaises(ValueError):
                ActivityReader({**self.metadata, "neuron_ids": ids})

    def test_readout_identity_and_metadata_alias_rejected(self):
        self.metadata["neuron_ids"][0] = "5"
        self.assertEqual(self.reader.ids[0], "720575940660219265")
        with self.assertRaises(ValueError):
            self.reader.accept({**self.response, "giant_fiber_spikes": {}})

    def test_sensorimotor_readouts_match_sparse_counts_without_changing_packet(self):
        reader=ActivityReader({**self.metadata,"sensorimotor_candidates":[{"root_id":"4"}]})
        response={**self.response,"sensorimotor_spikes":{"4":3}}
        self.assertEqual(reader.accept(response),self.response["neuron_activity"])
        for counts in [None,{"4":2},{"4":True},{"4":-1},{"missing":3}]:
            reader=ActivityReader({**self.metadata,"sensorimotor_candidates":[{"root_id":"4"}]})
            with self.subTest(counts=counts),self.assertRaises(ValueError):
                reader.accept({**self.response,"sensorimotor_spikes":counts})
            self.assertEqual(reader.sequence,0)

    def test_candidate_metadata_rejects_absent_duplicate_or_malformed_ids(self):
        for candidates in [[{"root_id":"missing"}],[{"root_id":"4"},{"root_id":"4"}],[{}],[None]]:
            with self.subTest(candidates=candidates),self.assertRaises(ValueError):
                ActivityReader({**self.metadata,"sensorimotor_candidates":candidates})


@unittest.skipUnless(
    os.environ.get("FLY_ACTIVITY_DATA_DIR") and os.environ.get("FLY_ACTIVITY_OUTPUT_DIR"),
    "Set explicit external data/output directories to run the real-network regression",
)
class ActualNetworkActivityTests(unittest.TestCase):
    def test_sensorimotor_readouts_do_not_change_visual_network(self):
        from datasets import ROOT
        from fly_feeding import BrainClient
        from fly_walking import external_output

        output = external_output(Path(os.environ["FLY_ACTIVITY_OUTPUT_DIR"])/"sensorimotor")
        output.mkdir(parents=True)
        responses = {}
        for telemetry in [False, True]:
            target=output/("readouts" if telemetry else "control")
            target.mkdir()
            client=BrainClient(
                ROOT/".venv/bin/python",Path(os.environ["FLY_ACTIVITY_DATA_DIR"]),
                target,420,takeoff=True,telemetry=telemetry,
            )
            try:
                client.begin_step(1000,False,True)
                response=client.finish_step()
                responses[telemetry]=response
                (target/"response.json").write_text(json.dumps(response)+"\n")
                if telemetry:
                    self.assertEqual(len(client.metadata["sensorimotor_candidates"]),39)
                    self.assertEqual(len(response["sensorimotor_spikes"]),39)
                    client.reset()
                    client.begin_step(1000,False,True)
                    replay=client.finish_step()
                    self.assertEqual(replay["sensorimotor_spikes"],response["sensorimotor_spikes"])
                    client.reset()
                    client.begin_step(1000,False,False)
                    silent=client.finish_step()
                    self.assertEqual(silent["network_spikes"],0)
                    self.assertTrue(all(value==0 for value in silent["sensorimotor_spikes"].values()))
            finally:
                client.close()
        self.assertEqual(responses[False],{
            key:value for key,value in responses[True].items()
            if key not in {"neuron_activity","sensorimotor_spikes"}
        })

    def test_baseline_conservation_reset_and_silent_control(self):
        from datasets import ROOT
        from fly_feeding import BrainClient
        from fly_walking import external_output

        output = external_output(Path(os.environ["FLY_ACTIVITY_OUTPUT_DIR"]))
        output.mkdir(parents=True)
        packets = {}
        for enabled in [False, True]:
            target = output / ("telemetry" if enabled else "control")
            target.mkdir()
            client = BrainClient(
                ROOT / ".venv/bin/python", Path(os.environ["FLY_ACTIVITY_DATA_DIR"]),
                target, 420, telemetry=enabled,
            )
            try:
                (target / "metadata.json").write_text(json.dumps(client.metadata) + "\n")

                def stimulus():
                    responses = []
                    for _ in range(10):
                        client.begin_step(100, True)
                        responses.append(client.finish_step())
                    return responses

                responses = stimulus()
                packets[enabled] = responses
                (target / "intervals.json").write_text(json.dumps(responses) + "\n")
                self.assertEqual(sum(row["mn9_spikes"] for row in responses), 65)
                self.assertEqual(sum(row["network_spikes"] for row in responses), 9840)
                if enabled:
                    client.reset()
                    replay = stimulus()
                    (target / "reset-replay.json").write_text(json.dumps(replay) + "\n")
                    for original, repeated in zip(responses, replay):
                        self.assertEqual(original["neuron_activity"]["indices"], repeated["neuron_activity"]["indices"])
                        self.assertEqual(original["neuron_activity"]["counts"], repeated["neuron_activity"]["counts"])
                        self.assertEqual(repeated["neuron_activity"]["episode"], 1)
                    client.reset()
                    client.begin_step(1000, False)
                    silent = client.finish_step()
                    (target / "no-input.json").write_text(json.dumps(silent) + "\n")
                    self.assertEqual(silent["network_spikes"], 0)
                    self.assertEqual(silent["neuron_activity"]["indices"], [])
            finally:
                client.close()
        for original, observed in zip(packets[False], packets[True]):
            self.assertEqual(original, {key: value for key, value in observed.items() if key != "neuron_activity"})
        (output / "summary.json").write_text(json.dumps({
            "status": "passed", "seed": 420, "mn9_spikes": 65, "network_spikes": 9840,
            "baseline_parity": True, "reset_replay": True, "no_input_silent": True,
        }, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
