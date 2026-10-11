"""Explicit external finger motion; wall time is not the neural clock."""

import math


def capped_motion(position, target, wall_duration_s, speed_mm_s=20):
    if (
        len(position) != 3 or len(target) != 3
        or any(not math.isfinite(value) for value in [*position, *target])
        or not math.isfinite(wall_duration_s) or wall_duration_s < 0
        or not math.isfinite(speed_mm_s) or speed_mm_s <= 0
    ):
        raise ValueError("Finger motion requires finite 3D positions, nonnegative time and positive speed")
    duration = min(wall_duration_s, .1)
    delta = [b-a for a, b in zip(position, target)]
    distance = math.sqrt(sum(value*value for value in delta))
    scale = min(1, speed_mm_s*duration/distance) if distance else 0
    return [a+value*scale for a, value in zip(position, delta)]
