"""Bounded foraging/feeding proxy over the pinned C. elegans topology."""

from __future__ import annotations

import math
import random

from worm_touch import relay_from_activity


MAX_STEP_S = 0.2
ARENA_RADIUS_MM = 17.5
MAX_HEAD_RADIUS_MM = 16.3
ODOR_SIGMA_MM = 1.15
FOOD_RADIUS_MM = 0.22
MAX_NEURAL_RATE_HZ = 20.0

SENSORY_LEFT = ("AWAL", "AWCL")
SENSORY_RIGHT = ("AWAR", "AWCR")
FORWARD_OUTPUT = ("AVBL", "AVBR")
FEEDING_OUTPUT = ("MCL", "MCR", "M3L", "M3R", "NSML", "NSMR")

ASSUMPTIONS = (
    "Bacterial concentration is an assumed attractive odor field, not a measured OP50 chemical gradient.",
    "Food cues are encoded into named AWA/AWC cells by an assumed left/right sensor model.",
    "Cook chemical edges relay positively and gap edges bidirectionally with 0.5 gain for at most four hops; signs and conductances are unavailable.",
    "AVB activity is decoded as forward drive; lateral sensory imbalance is decoded as turning.",
    "Food contact directly drives an assumed MC/M3/NSM feeding-rate proxy and depletes simulated food.",
    "Reported rates and event pulses are synthetic model outputs, not recorded voltages or spikes.",
    "The worm body is a 2D kinematic illustration without muscles, biomechanics, proprioception, or fluid dynamics.",
    "A geometric head-position clamp keeps the illustrative body inside the 17.5 mm-radius model dish; it is not neural boundary avoidance.",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


class WormForagingModel:
    def __init__(self, connectome: dict, seed: int = 420):
        self.connectome = connectome
        self.nodes = set(connectome["nodes"])
        self.seed = seed
        if not 0 < MAX_HEAD_RADIUS_MM < ARENA_RADIUS_MM:
            raise ValueError("Foraging head bound must lie inside the model dish")
        required = set(SENSORY_LEFT + SENSORY_RIGHT + FORWARD_OUTPUT + FEEDING_OUTPUT)
        missing = sorted(required - self.nodes)
        if missing:
            raise ValueError(f"Foraging proxy cell labels are absent from the pinned graph: {missing}")
        self.random = random.Random(seed)
        self.reset()

    def reset(self) -> dict:
        self.random.seed(self.seed)
        self.time_s = 0.0
        self.head_x = -1.55
        self.head_y = -0.2
        self.heading = 0.0
        self.food_patches = [
            {"id": "bacterial-patch-1", "x": 0.0, "y": -0.2, "biomass": 1.0},
            {"id": "bacterial-patch-2", "x": 0.6, "y": -0.7, "biomass": 1.0},
            {"id": "bacterial-patch-3", "x": 0.6, "y": 0.3, "biomass": 1.0},
        ]
        self.last_state = {
            "time_s": self.time_s,
            "pose": {"head_x": self.head_x, "head_y": self.head_y, "heading_rad": self.heading},
            "food_patches": self.food_patches.copy(),
            "food_cues": {"left": 0.0, "right": 0.0},
            "food_contact": False,
            "feeding_rate_proxy_hz": 0.0,
            "forward_drive_proxy": 0.0,
            "turn_drive_proxy": 0.0,
            "neuron_rates_hz": {},
            "spike_events": [],
            "activation": [],
            "relay_edges": [],
            "max_hop": 0,
            "assumptions": list(ASSUMPTIONS),
            "scope": "synthetic connectome-topology foraging/feeding proxy",
            "arena_radius_mm": ARENA_RADIUS_MM,
            "boundary_guard_active": False,
        }
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            **self.last_state,
            "pose": dict(self.last_state["pose"]),
            "food_patches": [dict(patch) for patch in self.food_patches],
            "food_cues": dict(self.last_state["food_cues"]),
            "neuron_rates_hz": dict(self.last_state["neuron_rates_hz"]),
            "spike_events": list(self.last_state["spike_events"]),
            "activation": [dict(item) for item in self.last_state["activation"]],
            "relay_edges": [dict(item) for item in self.last_state["relay_edges"]],
            "assumptions": list(ASSUMPTIONS),
        }

    def _food_cue(self, x: float, y: float) -> float:
        strength = sum(
            patch["biomass"] * math.exp(
                -((x - patch["x"]) ** 2 + (y - patch["y"]) ** 2) / (2 * ODOR_SIGMA_MM ** 2)
            )
            for patch in self.food_patches
        )
        return _clamp(strength / (0.35 + strength))

    def step(self, dt_s: float) -> dict:
        if (
            isinstance(dt_s, bool)
            or not isinstance(dt_s, (int, float))
            or not math.isfinite(dt_s)
            or dt_s <= 0
            or dt_s > MAX_STEP_S
        ):
            raise ValueError(f"Foraging timestep must be finite and between 0 and {MAX_STEP_S} seconds")

        forward = math.cos(self.heading), math.sin(self.heading)
        left = -forward[1], forward[0]
        sensor_x = self.head_x + forward[0] * 0.08
        sensor_y = self.head_y + forward[1] * 0.08
        sensor_offset = 0.09
        left_cue = self._food_cue(sensor_x + left[0] * sensor_offset, sensor_y + left[1] * sensor_offset)
        right_cue = self._food_cue(sensor_x - left[0] * sensor_offset, sensor_y - left[1] * sensor_offset)

        sensory_activity = {
            "AWAL": left_cue,
            "AWCL": left_cue * 0.7,
            "AWAR": right_cue,
            "AWCR": right_cue * 0.7,
        }
        relay = relay_from_activity(self.connectome, sensory_activity)
        activation = {item["cell"]: item["level"] for item in relay["activation"]}
        cue_strength = max(left_cue, right_cue)
        avb_drive = sum(activation.get(cell, 0.0) for cell in FORWARD_OUTPUT) / len(FORWARD_OUTPUT)
        forward_drive = _clamp(avb_drive * 1.8) if cue_strength > 0.01 else 0.0

        left_motor = sum(activation.get(cell, 0.0) for cell in ("AVAL", "AVDL"))
        right_motor = sum(activation.get(cell, 0.0) for cell in ("AVAR", "AVDR"))
        sensory_bias = left_cue - right_cue
        turn_drive = _clamp(0.7 * sensory_bias + 0.3 * (left_motor - right_motor), -1.0, 1.0)
        commanded_speed_mm_s = 0.28 * forward_drive
        self.heading += turn_drive * 1.25 * dt_s
        previous_x, previous_y = self.head_x, self.head_y
        next_x = self.head_x + math.cos(self.heading) * commanded_speed_mm_s * dt_s
        next_y = self.head_y + math.sin(self.heading) * commanded_speed_mm_s * dt_s
        boundary_guard_active = math.hypot(next_x, next_y) > MAX_HEAD_RADIUS_MM
        if boundary_guard_active:
            radius = math.hypot(next_x, next_y)
            self.head_x = next_x * MAX_HEAD_RADIUS_MM / radius
            self.head_y = next_y * MAX_HEAD_RADIUS_MM / radius
        else:
            self.head_x, self.head_y = next_x, next_y
        speed_mm_s = math.hypot(self.head_x - previous_x, self.head_y - previous_y) / dt_s

        distance_to_food = [
            math.hypot(self.head_x - patch["x"], self.head_y - patch["y"])
            for patch in self.food_patches
        ]
        nearest = min(range(len(distance_to_food)), key=distance_to_food.__getitem__) if distance_to_food else None
        food_contact = bool(
            nearest is not None
            and distance_to_food[nearest] <= FOOD_RADIUS_MM
            and self.food_patches[nearest]["biomass"] > 0
        )
        feeding_rate = 5.0 if food_contact else 0.0
        if food_contact:
            self.food_patches[nearest]["biomass"] = max(
                0.0, self.food_patches[nearest]["biomass"] - 0.04 * dt_s
            )

        neuron_rates = {
            cell: min(MAX_NEURAL_RATE_HZ, level * MAX_NEURAL_RATE_HZ)
            for cell, level in activation.items()
            if level > 0
        }
        if food_contact:
            for cell in FEEDING_OUTPUT:
                neuron_rates[cell] = feeding_rate
        spike_events = sorted(
            cell for cell, rate in neuron_rates.items()
            if self.random.random() < min(1.0, rate * dt_s)
        )

        self.time_s += dt_s
        self.last_state = {
            "time_s": self.time_s,
            "pose": {
                "head_x": self.head_x,
                "head_y": self.head_y,
                "heading_rad": self.heading,
                "speed_mm_s": speed_mm_s,
                "speed_command_mm_s": commanded_speed_mm_s,
            },
            "food_patches": self.food_patches.copy(),
            "food_cues": {"left": left_cue, "right": right_cue},
            "food_contact": food_contact,
            "feeding_rate_proxy_hz": feeding_rate,
            "forward_drive_proxy": forward_drive,
            "turn_drive_proxy": turn_drive,
            "neuron_rates_hz": neuron_rates,
            "spike_events": spike_events,
            "activation": relay["activation"],
            "relay_edges": relay["relay_edges"],
            "max_hop": relay["max_hop"],
            "assumptions": list(ASSUMPTIONS),
            "scope": "synthetic connectome-topology foraging/feeding proxy",
            "arena_radius_mm": ARENA_RADIUS_MM,
            "boundary_guard_active": boundary_guard_active,
        }
        return self.snapshot()
