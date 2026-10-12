"""Causal interval-boundary spike-count relay; all transmission gains are assumed."""

import math

from export_bdn2_packets import BDN2_IDS


DECAY_S = .04
MODEL_CURRENT_PER_SPIKE = 62.5
INTERVAL_MS = 10
SCOPE = (
    "Actual left female FlyWire BDN2 interval counts -> assumed exponential "
    "current relay -> separately matched male MANC BDN2 rate circuit. "
    "62.5model units/spike and40ms decay map100Hz to mean250model units; "
    "not a measured conductance, membrane current or identity equality."
)


class CountRelay:
    def __init__(self, connected=True, current_per_spike=MODEL_CURRENT_PER_SPIKE, decay_s=DECAY_S):
        if type(connected) is not bool:
            raise ValueError("Relay connection state must be explicit Boolean")
        if (type(current_per_spike) not in (int, float) or type(decay_s) not in (int, float)
                or not math.isfinite(current_per_spike) or not math.isfinite(decay_s)
                or current_per_spike <= 0 or decay_s <= 0):
            raise ValueError("Research relay gain and decay must be positive finite parameters")
        self.connected = connected
        self.current_per_spike, self.decay_s = float(current_per_spike), float(decay_s)
        self.current = 0.
        self.sequence = 0
        self.end_ms = 0.
        self.episode = None
        self.total_source_spikes = 0

    def validate(self, response):
        packet = response.get("neuron_activity")
        counts = response.get("sensorimotor_spikes")
        if not isinstance(packet, dict) or not isinstance(counts, dict):
            raise ValueError("Relay requires a verified exact activity/count packet")
        sequence, episode = packet.get("sequence"), packet.get("episode")
        start, end = packet.get("start_ms"), packet.get("end_ms")
        count = counts.get(BDN2_IDS["left"])
        if (type(sequence) is not int or sequence != self.sequence+1
                or type(episode) is not int or episode < 0
                or self.episode is not None and episode != self.episode
                or type(start) not in (int, float) or type(end) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(end)
                or abs(start-self.end_ms) > 1e-7 or abs(end-start-INTERVAL_MS) > 1e-7
                or response.get("brain_time_ms") != end
                or type(count) is not int or count < 0):
            raise ValueError("Relay rejects stale, gapped, wrong-episode or invalid neural counts/clocks")
        return count, episode, float(end)

    def accept(self, response):
        count, episode, end = self.validate(response)
        self.current *= math.exp(-INTERVAL_MS*.001/self.decay_s)
        delivered = count if self.connected else 0
        self.current += self.current_per_spike*delivered
        self.sequence += 1
        self.end_ms, self.episode = end, episode
        self.total_source_spikes += count
        return {"source_count": count, "delivered_count": delivered,
                "delivery_ms": end, "current_model_units": self.current}
