"""Unit-explicit gap-junction currents; no inferred fly conductances."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GapJunction:
    first_id: str
    second_id: str
    conductance_uS: float

    def __post_init__(self):
        if (
            not isinstance(self.first_id, str) or not isinstance(self.second_id, str)
            or not self.first_id or not self.second_id or self.first_id == self.second_id
        ):
            raise ValueError("A gap junction requires two distinct exact neuron IDs")
        if (
            isinstance(self.conductance_uS, bool)
            or not isinstance(self.conductance_uS, (int, float))
            or not math.isfinite(self.conductance_uS) or self.conductance_uS < 0
        ):
            raise ValueError("Conductance must be an explicit finite nonnegative value in microSiemens")


def currents_nA(junctions, voltages_mV):
    result = {neuron: 0.0 for neuron in voltages_mV}
    if any(
        isinstance(voltage, bool) or not isinstance(voltage, (int, float))
        or not math.isfinite(voltage) for voltage in voltages_mV.values()
    ):
        raise ValueError("Membrane potentials must be finite millivolt values")
    seen = set()
    for junction in junctions:
        pair = frozenset((junction.first_id, junction.second_id))
        if pair in seen:
            raise ValueError("Duplicate electrical junction; do not double-count opposite directions")
        seen.add(pair)
        if not pair <= voltages_mV.keys():
            raise ValueError("Electrical junction references a missing membrane potential")
        current = junction.conductance_uS * (
            voltages_mV[junction.second_id] - voltages_mV[junction.first_id]
        )
        result[junction.first_id] += current
        result[junction.second_id] -= current
    return result
