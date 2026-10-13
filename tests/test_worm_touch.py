import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from worm_touch import relay_from_cells, simulate_anterior_touch, validate_touch_event


class WormTouchTests(unittest.TestCase):
    def setUp(self):
        self.connectome = {
            "nodes": ["ALML", "ALMR", "AVM", "AVDR", "AVBL", "DA01", "VB01"],
            "edges": [
                {"source": "ALML", "target": "AVDR", "kind": "chemical", "weight_sections": 3},
                {"source": "ALML", "target": "AVM", "kind": "electrical_gap_junction", "weight_sections": 7},
                {"source": "ALMR", "target": "AVM", "kind": "electrical_gap_junction", "weight_sections": 16},
                {"source": "AVM", "target": "AVDR", "kind": "chemical", "weight_sections": 1},
                {"source": "AVM", "target": "AVBL", "kind": "chemical", "weight_sections": 13},
                {"source": "AVDR", "target": "DA01", "kind": "chemical", "weight_sections": 6},
                {"source": "AVBL", "target": "VB01", "kind": "chemical", "weight_sections": 6},
            ],
        }

    def test_touch_uses_measured_edges_and_selects_backward_motor_route(self):
        result = simulate_anterior_touch(self.connectome)
        self.assertIn("AVDR", result["highlight_cells"])
        self.assertIn("DA01", result["highlight_cells"])
        self.assertGreater(result["backward_score"], result["forward_score"])
        self.assertEqual(result["movement_command"], "backward")
        self.assertIn(["ALML", "AVDR", "DA01"], [route["cells"] for route in result["backward_motor_routes"]])

    def test_no_sensory_input_has_no_motor_command(self):
        result = relay_from_cells(self.connectome, [])
        self.assertEqual(result["movement_command"], "undetermined")
        self.assertEqual(result["activation"], [])

    def test_motor_disconnect_removes_the_touch_reversal_output(self):
        disconnected = {
            **self.connectome,
            "edges": [
                edge for edge in self.connectome["edges"]
                if not (edge["source"] == "AVDR" and edge["target"] == "DA01")
            ],
        }
        result = simulate_anterior_touch(disconnected)
        self.assertEqual(result["backward_score"], 0)
        self.assertGreater(result["forward_score"], 0)
        self.assertEqual(result["movement_command"], "forward")

    def test_unknown_touch_cell_fails_instead_of_silently_falling_back(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            simulate_anterior_touch({"nodes": ["ALML"], "edges": []})

    def test_only_the_documented_touch_event_is_accepted(self):
        event = {"kind": "anterior_touch"}
        self.assertEqual(validate_touch_event(event), event)
        for invalid in (
            {"kind": "odor"},
            {"kind": "anterior_touch", "force": 0.5},
            [],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_touch_event(invalid)


if __name__ == "__main__":
    unittest.main()
