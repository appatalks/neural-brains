import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_objects import Objects


class ObjectTests(unittest.TestCase):
    def test_place_clamps_and_uses_ground_height(self):
        objects = Objects(30)
        box = objects.place("box", [100, -100, 12])
        self.assertEqual(box["position_mm"], [29.2, -29.2, 0.8])
        self.assertEqual(box["name"], "placed_box_0")
        sphere = objects.place("sphere", [1, 2, 3])
        self.assertEqual(sphere["name"], "placed_sphere_0")
        self.assertEqual(objects.remove(), sphere)

    def test_slot_exhaustion_and_remove(self):
        objects = Objects(30)
        for _ in range(3):
            objects.place("box", [0, 0, 0])
        with self.assertRaises(ValueError):
            objects.place("box", [0, 0, 0])
        objects.remove()
        self.assertEqual(objects.place("box", [0, 0, 0])["name"], "placed_box_2")

    def test_saved_placements_reload_exactly(self):
        objects = Objects(30)
        objects.place("box", [1, 2, 0])
        objects.place("sphere", [3, 4, 0])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "objects.json"
            path.write_text(json.dumps(objects.placements))
            restored = Objects(30)
            restored.load(path)
            self.assertEqual(restored.placements, objects.placements)

    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):
            Objects(30).place("box", [float("nan"), 0, 0])
        with self.assertRaises(ValueError):
            Objects(30).place("unknown", [0, 0, 0])
