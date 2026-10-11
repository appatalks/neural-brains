"""Bounded physical object placement with explicit saved scene edits."""

import json
import math
from pathlib import Path


SLOTS = [(f"placed_box_{i}", "box", 0.8) for i in range(3)] + [
    (f"placed_sphere_{i}", "sphere", 0.8) for i in range(3)
]


class Objects:
    def __init__(self, half_size):
        self.half_size = half_size
        self.placements = []

    def place(self, kind, target):
        if kind not in {"box", "sphere"}:
            raise ValueError("Unknown placeable object type")
        if len(target) != 3 or any(not math.isfinite(value) for value in target):
            raise ValueError("Object target must contain finite world coordinates")
        used = {item["name"] for item in self.placements}
        slot = next((slot for slot in SLOTS if slot[1] == kind and slot[0] not in used), None)
        if slot is None:
            raise ValueError(f"All three {kind} slots are occupied; remove an object first")
        name, kind, radius = slot
        limit = self.half_size - radius
        item = {
            "name": name, "kind": kind, "size_mm": radius,
            "position_mm": [max(-limit, min(limit, target[0])), max(-limit, min(limit, target[1])), radius],
        }
        self.placements.append(item)
        return item

    def remove(self):
        if not self.placements:
            raise ValueError("No placed object to remove")
        return self.placements.pop()

    def load(self, path: Path):
        entries = json.loads(path.read_text())
        if not isinstance(entries, list):
            raise ValueError("Object scene file must contain a list")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"name", "kind", "size_mm", "position_mm"}:
                raise ValueError("Invalid saved object fields")
            item = self.place(entry["kind"], entry["position_mm"])
            if item != entry:
                raise ValueError("Saved object slots/sizes/positions do not match supported scene contract")
