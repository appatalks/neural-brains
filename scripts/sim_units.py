"""Explicit physical-unit conversion at simulation backend boundaries."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicsUnits:
    length_m: float
    mass_kg: float

    def __post_init__(self):
        if not all(math.isfinite(value) and value > 0 for value in (self.length_m, self.mass_kg)):
            raise ValueError("Base length and mass units must be finite and positive")

    def _finite(self, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Physical quantities must be finite")
        return value

    def force_from_micro_newtons(self, value: float) -> float:
        return self._finite(value) / (self.mass_kg * self.length_m * 1e6)

    def length_from_mm(self, value: float) -> float:
        return self._finite(value) / (self.length_m * 1000)

    def length_to_mm(self, value: float) -> float:
        return self._finite(value) * (self.length_m * 1000)

    def mass_from_mg(self, value: float) -> float:
        return self._finite(value) * 1e-6 / self.mass_kg


WALKING_UNITS = PhysicsUnits(length_m=0.001, mass_kg=0.001)
FLIGHT_UNITS = PhysicsUnits(length_m=0.01, mass_kg=0.001)


def simulation_steps(duration_s: float, timestep_s: float) -> int:
    if (
        not math.isfinite(duration_s) or duration_s <= 0
        or not math.isfinite(timestep_s) or timestep_s <= 0
    ):
        raise ValueError("Duration and timestep must be finite and positive")
    steps = round(duration_s / timestep_s)
    if steps < 1 or abs(steps * timestep_s - duration_s) > 1e-9:
        raise ValueError("Duration must be an integer number of simulation timesteps")
    return steps
