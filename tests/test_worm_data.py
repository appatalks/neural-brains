import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from worm_data import matrix_edges, parse_recording_spec, validate_trace


class WormDataTests(unittest.TestCase):
    def test_chemical_matrix_preserves_direction_and_self_connections(self):
        edges, self_entries = matrix_edges(
            ["A", "B"], ["A", "B"], [[2, 3], [0, 4]], "chemical"
        )
        self.assertEqual(
            [(edge["source"], edge["target"], edge["weight_sections"]) for edge in edges],
            [("A", "A", 2), ("A", "B", 3), ("B", "B", 4)],
        )
        self.assertEqual(self_entries, [])

    def test_symmetric_gap_matrix_emits_one_undirected_pair_and_reports_diagonal(self):
        edges, self_entries = matrix_edges(
            ["A", "B"], ["B", "A"], [[5, 0], [2, 5]], "electrical_gap_junction"
        )
        self.assertEqual(
            [(edge["source"], edge["target"], edge["weight_sections"]) for edge in edges],
            [("A", "B", 5)],
        )
        self.assertEqual(self_entries, [{"cell": "B", "weight_sections": 2}])

    def test_gap_asymmetry_and_invalid_weights_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "not symmetric"):
            matrix_edges(["A", "B"], ["A", "B"], [[0, 2], [1, 0]], "electrical_gap_junction")
        with self.assertRaisesRegex(ValueError, "Invalid connectivity weight"):
            matrix_edges(["A"], ["A"], [[-1]], "chemical")

    def test_trace_times_and_values_must_match_and_timestamps_may_repeat(self):
        self.assertEqual(validate_trace([0, 0.5, 0.5], [1, 2, 3], "A"), ([0.0, 0.5, 0.5], [1.0, 2.0, 3.0]))
        for times, values in (([0, 1], [1]), ([1, 0], [1, 2]), ([0, float("nan")], [1, 2])):
            with self.subTest(times=times), self.assertRaises(ValueError):
                validate_trace(times, values, "A")

    def test_recording_selection_rejects_paths_and_requires_explicit_worm(self):
        self.assertEqual(parse_recording_spec("WT_NoStim.mat=worm7"), ("WT_NoStim.mat", "worm7"))
        for value in ("WT_NoStim.mat", "../WT_NoStim.mat=worm7", "dir/WT_NoStim.mat=worm7", "x.txt=worm0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_recording_spec(value)


if __name__ == "__main__":
    unittest.main()
