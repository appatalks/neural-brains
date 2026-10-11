"""Bounded wall-time phase measurements, independent of scientific clocks."""

import time
from contextlib import contextmanager


class PhaseTimings:
    def __init__(self):
        self.values = {}

    @contextmanager
    def measure(self, phase):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            row = self.values.setdefault(phase, {"calls": 0, "seconds": 0.0, "maximum_seconds": 0.0})
            row["calls"] += 1
            row["seconds"] += elapsed
            row["maximum_seconds"] = max(row["maximum_seconds"], elapsed)

    def snapshot(self):
        return {phase: {**row, "mean_ms": row["seconds"]*1000/row["calls"]}
                for phase, row in self.values.items()}
