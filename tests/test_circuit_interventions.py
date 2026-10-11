import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_circuit_interventions import outgoing_edge_indices, visual_output_targets
from fly_feeding import BrainClient


class ChemicalDisconnectionTests(unittest.TestCase):
    def test_only_selected_outgoing_edges_are_disconnected(self):
        self.assertEqual(outgoing_edge_indices([0, 1, 0, 2, 3], [0, 3]).tolist(), [0, 2, 4])
        self.assertEqual(outgoing_edge_indices([0, 1], [2]).tolist(), [])

    def test_exact_verified_population_selection(self):
        rows = [
            {"population":"LC4", "root_id":"1", "in_model":True},
            {"population":"LPLC2", "root_id":"2", "in_model":True},
            {"population":"GF", "root_id":"3", "in_model":True},
        ]
        self.assertEqual(visual_output_targets(rows, "both"), ["1", "2"])
        self.assertEqual(visual_output_targets(rows, "LC4"), ["1"])
        for population in ["GF", "LC40", "invalid"]:
            with self.assertRaises(ValueError):
                visual_output_targets(rows, population)
        rows[0]["in_model"] = False
        with self.assertRaises(ValueError):
            visual_output_targets(rows, "LC4")

    def test_invalid_indices_and_non_takeoff_use_rejected(self):
        for sources, targets in [([0, 1], []), ([0, 1], [1, 1]), ([-1, 0], [0]),
                                 ([0, 1], [True]), ([0.5], [0])]:
            with self.assertRaises(ValueError):
                outgoing_edge_indices(sources, targets)
        with self.assertRaises(ValueError):
            BrainClient(Path("/unused"), Path("/unused"), Path("/unused"), 420,
                        disconnect_visual_output="LC4")
