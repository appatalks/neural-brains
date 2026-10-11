"""DNp10-driven reduced VNC/activation surrogate, not measured muscle physiology."""

import math


DNP10_IDS = {"left": "720575940620153765", "right": "720575940619678366"}
SCOPE = (
    "Actual FlyWire DNp10 spikes -> assumed bilateral reduced VNC/activation "
    "surrogate -> FlyBody leg position actuators. Not measured muscle recruitment "
    "or touchdown; DNp07 is not decoded."
)
DECAY_S = 0.08
RECRUITMENT_PER_SPIKE = 0.35
TIBIA_EXTENSION_RAD = 0.9


def verified_dnp10(metadata):
    rows = [row for row in metadata.get("sensorimotor_candidates", [])
            if row.get("population") == "DNp10"]
    if (
        len(rows) != 2
        or {row.get("side"): row.get("root_id") for row in rows} != DNP10_IDS
        or any(not row.get("in_model") or row.get("ambiguous_type_correspondence") for row in rows)
    ):
        raise ValueError("Leg extension requires the exact verified FlyWire630 DNp10 pair")
    return list(DNP10_IDS.values())


class LegExtension:
    def __init__(self, metadata):
        self.ids = verified_dnp10(metadata)
        self.reset()

    def reset(self):
        self.activation = 0.0
        self.sequence = 0
        self.end_ms = 0.0
        self.episode = None
        self.total_spikes = 0

    def accept(self, response):
        packet = response["neuron_activity"]
        if (
            packet["sequence"] != self.sequence + 1
            or packet["start_ms"] != self.end_ms
            or self.episode is not None and packet["episode"] != self.episode
        ):
            raise ValueError("Extension requires contiguous, unreplayed neural intervals")
        counts = response["sensorimotor_spikes"]
        if any(type(counts.get(value)) is not int or counts[value] < 0 for value in self.ids):
            raise ValueError("Extension requires exact nonnegative DNp10 spike counts")
        count = sum(counts[value] for value in self.ids)
        # Counts are delivered at the interval boundary, never assigned fake
        # within-interval spike times or applied to the body's past interval.
        self.activation = 1 - (1 - self.activation) * math.exp(-RECRUITMENT_PER_SPIKE * count)
        self.total_spikes += count
        self.sequence = packet["sequence"]
        self.end_ms = packet["end_ms"]
        self.episode = packet["episode"]

    def advance(self, duration_s, flying):
        if not math.isfinite(duration_s) or duration_s <= 0 or type(flying) is not bool:
            raise ValueError("Extension needs a positive physical timestep and explicit flight state")
        self.activation *= math.exp(-duration_s / DECAY_S)
        return self.activation if flying else 0.0

    def snapshot(self):
        return {"scope": SCOPE, "activation": self.activation, "dnp10_spikes": self.total_spikes,
                "neural_interval_end_ms": self.end_ms, "decay_s": DECAY_S,
                "recruitment_per_spike": RECRUITMENT_PER_SPIKE,
                "tibia_extension_rad": TIBIA_EXTENSION_RAD,
                "delivery": "interval boundary; next physical interval only",
                "bilateral_recruitment": "assumed symmetric six-leg response; not side-specific anatomy"}
