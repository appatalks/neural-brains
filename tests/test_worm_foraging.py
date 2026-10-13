import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from worm_foraging import MAX_HEAD_RADIUS_MM, WormForagingModel


class WormForagingTests(unittest.TestCase):
    def setUp(self):
        cells = (
            "AWAL", "AWAR", "AWCL", "AWCR",
            "AVBL", "AVBR", "AVAL", "AVAR", "AVDL", "AVDR",
            "MCL", "MCR", "M3L", "M3R", "NSML", "NSMR",
        )
        self.connectome = {
            "nodes": list(cells),
            "edges": [
                {"source": "AWAL", "target": "AVBL", "kind": "chemical", "weight_sections": 3},
                {"source": "AWAR", "target": "AVBR", "kind": "chemical", "weight_sections": 3},
                {"source": "AWCL", "target": "AVAL", "kind": "chemical", "weight_sections": 2},
                {"source": "AWCR", "target": "AVAR", "kind": "chemical", "weight_sections": 2},
                {"source": "AVBL", "target": "MCL", "kind": "chemical", "weight_sections": 1},
            ],
        }

    def test_food_cues_generate_separate_synthetic_activity_and_motor_state(self):
        model = WormForagingModel(self.connectome)
        before = model.snapshot()
        state = model.step(0.1)
        self.assertEqual(before["neuron_rates_hz"], {})
        self.assertEqual(state["scope"], "synthetic connectome-topology foraging/feeding proxy")
        self.assertTrue(state["neuron_rates_hz"])
        self.assertTrue(state["activation"])
        self.assertIn("AWAL", state["neuron_rates_hz"])
        self.assertTrue(state["assumptions"])
        self.assertNotEqual(
            (state["pose"]["head_x"], state["pose"]["head_y"]),
            (before["pose"]["head_x"], before["pose"]["head_y"]),
        )

    def test_no_food_cue_produces_silence_and_no_motion(self):
        model = WormForagingModel(self.connectome)
        model.food_patches = []
        before = model.snapshot()
        state = model.step(0.1)
        self.assertEqual(state["neuron_rates_hz"], {})
        self.assertEqual(state["spike_events"], [])
        self.assertEqual(
            (state["pose"]["head_x"], state["pose"]["head_y"]),
            (before["pose"]["head_x"], before["pose"]["head_y"]),
        )

    def test_food_contact_raises_assumed_pumping_and_depletes_patch(self):
        model = WormForagingModel(self.connectome)
        patch = model.food_patches[0]
        model.head_x, model.head_y = patch["x"], patch["y"]
        initial_biomass = patch["biomass"]
        state = model.step(0.1)
        self.assertTrue(state["food_contact"])
        self.assertGreater(state["feeding_rate_proxy_hz"], 0)
        self.assertLess(state["food_patches"][0]["biomass"], initial_biomass)
        self.assertIn("MCL", state["neuron_rates_hz"])
        self.assertIn("NSML", state["neuron_rates_hz"])

    def test_schematic_dish_clamp_is_bounded_and_reported(self):
        model = WormForagingModel(self.connectome)
        model.head_x, model.head_y, model.heading = MAX_HEAD_RADIUS_MM - 0.001, 0.0, 0.0
        model.food_patches = [{"id": "edge", "x": MAX_HEAD_RADIUS_MM + 0.15, "y": 0.0, "biomass": 1.0}]

        state = model.step(0.2)

        self.assertTrue(state["boundary_guard_active"])
        self.assertEqual(state["arena_radius_mm"], 17.5)
        self.assertLessEqual(
            (state["pose"]["head_x"] ** 2 + state["pose"]["head_y"] ** 2) ** 0.5,
            MAX_HEAD_RADIUS_MM,
        )

    def test_reset_replays_seeded_synthetic_events(self):
        model = WormForagingModel(self.connectome)
        first = model.step(0.1)
        model.reset()
        replay = model.step(0.1)

        self.assertEqual(first["neuron_rates_hz"], replay["neuron_rates_hz"])
        self.assertEqual(first["spike_events"], replay["spike_events"])
        self.assertEqual(first["pose"], replay["pose"])

    def test_invalid_timestep_is_rejected(self):
        model = WormForagingModel(self.connectome)
        for dt in (0, -0.1, 0.21, float("nan"), True):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                model.step(dt)

    def test_missing_assumed_cells_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            WormForagingModel({"nodes": ["AWA"], "edges": []})


if __name__ == "__main__":
    unittest.main()
