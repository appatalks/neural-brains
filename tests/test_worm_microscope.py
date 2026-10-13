import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from worm_microscope import DEFAULT_PORT, HTML_PATH, server_address, validate_model, validate_port


class WormMicroscopeTests(unittest.TestCase):
    def test_only_the_single_interactive_port_is_allowed(self):
        self.assertEqual(validate_port(DEFAULT_PORT), 8840)
        self.assertEqual(server_address(DEFAULT_PORT), ("127.0.0.1", 8840))
        for port in (0, 8080, 8841, True, -1):
            with self.subTest(port=port), self.assertRaises(ValueError):
                validate_port(port)

    def test_worm_model_keeps_chemical_direction_and_gap_edges_undirected(self):
        model = {
            "schema_version": 1,
            "connectome": {
                "sex": "hermaphrodite",
                "nodes": ["A", "B"],
                "edges": [
                    {"source": "A", "target": "B", "kind": "chemical", "weight_sections": 2},
                    {"source": "A", "target": "B", "kind": "electrical_gap_junction", "weight_sections": 3},
                ],
                "edge_counts": {
                    "chemical_directed": 1,
                    "electrical_gap_undirected": 1,
                    "chemical_self_entries_retained": 0,
                    "electrical_diagonal_entries_excluded": 0,
                },
                "electrical_diagonal_entries": [],
            },
            "activity": {
                "recordings": [{
                    "recording_id": "Kato2015/WT_NoStim.mat/worm7",
                    "time_s": [0.0, 0.0, 0.5],
                    "sample_count": 3,
                    "matched_trace_count": 1,
                    "unlabeled_trace_rows": 0,
                    "unmatched_labeled_count": 0,
                    "unmatched_labeled_cells": [],
                    "traces": [{"cell": "A", "slot": 0, "calcium": [1.0, 1.2, 1.1]}],
                }],
            },
        }
        self.assertIs(validate_model(model), model)
        bad = {**model, "schema_version": True}
        with self.assertRaises(ValueError):
            validate_model(bad)
        bad_edges = {**model, "connectome": {**model["connectome"], "edges": [
            *model["connectome"]["edges"],
            {"source": "B", "target": "A", "kind": "electrical_gap_junction", "weight_sections": 3},
        ], "edge_counts": {
            "chemical_directed": 1,
            "electrical_gap_undirected": 2,
            "chemical_self_entries_retained": 0,
            "electrical_diagonal_entries_excluded": 0,
        }}}
        with self.assertRaisesRegex(ValueError, "unique undirected"):
            validate_model(bad_edges)

    def test_microscope_page_discloses_preview_scope_and_controls(self):
        html = HTML_PATH.read_text(encoding="utf-8")
        for text in (
            "C. elegans",
            "Microscope controls",
            "Enter fullscreen",
            "Activity map",
            "Recorded calcium playback",
            "Apply anterior touch pulse",
            "All electrical gap junctions",
            "never drives movement",
            "Center specimen",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)


if __name__ == "__main__":
    unittest.main()
