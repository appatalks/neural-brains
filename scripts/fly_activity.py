"""Exact, bounded per-interval spike counts; no inferred event times."""

import math


def validate_neuron_ids(neuron_ids):
    if (
        not isinstance(neuron_ids, list) or not neuron_ids
        or any(not isinstance(value, str) or not value.isascii() or not value.isdecimal() for value in neuron_ids)
        or len(set(neuron_ids)) != len(neuron_ids)
    ):
        raise ValueError("Activity metadata requires unique decimal string neuron IDs")


class ActivityReader:
    def __init__(self, metadata):
        self.ids = list(metadata["neuron_ids"])
        validate_neuron_ids(self.ids)
        if len(self.ids) != metadata["neurons"]:
            raise ValueError("Activity neuron IDs disagree with network size")
        mapping = {value: index for index, value in enumerate(self.ids)}
        self.mn9_id = metadata["mn9_id"]
        self.gf_ids = set(metadata["gf_ids"])
        self.readouts = {value: mapping[value] for value in [metadata["mn9_id"], *metadata["gf_ids"]]}
        candidates = metadata.get("sensorimotor_candidates", [])
        if not isinstance(candidates, list) or any(
            not isinstance(row, dict) or "root_id" not in row for row in candidates
        ):
            raise ValueError("Sensorimotor candidate metadata must be a list")
        candidate_ids = [row["root_id"] for row in candidates]
        if candidates:
            validate_neuron_ids(candidate_ids)
            if any(value not in mapping for value in candidate_ids):
                raise ValueError("Sensorimotor readout identity is absent from network")
        self.sensorimotor = {value: mapping[value] for value in candidate_ids}
        self.episode = 0
        self.sequence = 0
        self.end_ms = 0.0

    def accept(self, response, reset=False):
        packet = response.get("neuron_activity")
        fields = {
            "schema_version", "episode", "sequence", "start_ms", "end_ms",
            "indices", "counts", "network_spikes",
        }
        if not isinstance(packet, dict) or set(packet) != fields or type(packet["schema_version"]) is not int or packet["schema_version"] != 1:
            raise ValueError("Invalid sparse neuron activity schema")
        episode = self.episode + 1 if reset else self.episode
        sequence = 0 if reset else self.sequence + 1
        for name, expected in [("episode", episode), ("sequence", sequence)]:
            if type(packet[name]) is not int or packet[name] != expected:
                raise ValueError(f"Stale or out-of-order activity {name}")
        for name in ["start_ms", "end_ms"]:
            value = packet[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Activity clock must be finite milliseconds")
        expected_start = 0.0 if reset else self.end_ms
        if abs(packet["start_ms"] - expected_start) > 1e-7:
            raise ValueError("Activity intervals must be contiguous")
        if reset:
            if packet["end_ms"] != 0 or response.get("brain_time_ms") != 0:
                raise ValueError("Reset activity clock must be zero")
        elif (
            packet["end_ms"] <= packet["start_ms"]
            or abs(packet["end_ms"] - response["brain_time_ms"]) > 1e-7
            or abs(packet["end_ms"] - packet["start_ms"] - response["duration_ms"]) > 1e-7
        ):
            raise ValueError("Activity interval disagrees with neural clock")
        indices, counts = packet["indices"], packet["counts"]
        if (
            not isinstance(indices, list) or not isinstance(counts, list)
            or len(indices) != len(counts) or len(indices) > len(self.ids)
            or any(type(index) is not int or not 0 <= index < len(self.ids) for index in indices)
            or any(a >= b for a, b in zip(indices, indices[1:]))
            or any(type(count) is not int or count <= 0 for count in counts)
            or type(packet["network_spikes"]) is not int
            or sum(counts) != packet["network_spikes"]
        ):
            raise ValueError("Invalid sparse indices/counts or nonconserved spike total")
        if reset:
            if indices or packet["network_spikes"]:
                raise ValueError("Reset activity must be empty")
        else:
            if packet["network_spikes"] != response["network_spikes"]:
                raise ValueError("Activity count differs from network readout")
            if set(response["giant_fiber_spikes"]) != self.gf_ids:
                raise ValueError("Activity giant-fiber identities disagree with metadata")
            sparse = dict(zip(indices, counts))
            readouts = {**response["giant_fiber_spikes"], self.mn9_id: response["mn9_spikes"]}
            for value, count in readouts.items():
                if value not in self.readouts or sparse.get(self.readouts[value], 0) != count:
                    raise ValueError("Sparse activity disagrees with individual readout")
            if self.sensorimotor:
                counts_by_id = response.get("sensorimotor_spikes")
                if (
                    not isinstance(counts_by_id, dict) or set(counts_by_id) != set(self.sensorimotor)
                    or any(type(count) is not int or count < 0 for count in counts_by_id.values())
                    or any(sparse.get(self.sensorimotor[value], 0) != count for value, count in counts_by_id.items())
                ):
                    raise ValueError("Sensorimotor readouts disagree with exact sparse neuron activity")
        self.episode, self.sequence, self.end_ms = episode, sequence, packet["end_ms"]
        return packet


def activity_packet(delta_counts, episode, sequence, start_ms, end_ms):
    indices = [index for index, count in enumerate(delta_counts) if count]
    counts = [int(delta_counts[index]) for index in indices]
    return {
        "schema_version": 1, "episode": episode, "sequence": sequence,
        "start_ms": start_ms, "end_ms": end_ms, "indices": indices,
        "counts": counts, "network_spikes": sum(counts),
    }
