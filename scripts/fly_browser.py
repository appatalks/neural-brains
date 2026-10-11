"""Validated browser camera/environment inputs for the authoritative habitat."""

import math


ENVIRONMENT_KEYS = frozenset("POFBRCTHQ123[]")


def validate_input(value):
    if not isinstance(value, dict):
        raise ValueError("App input must be an object")
    kind = value.get("kind")
    fields = {
        "key": {"kind", "key"}, "pointer": {"kind", "x", "y"},
        "orbit": {"kind", "dx", "dy"}, "pan": {"kind", "dx", "dy"},
        "zoom": {"kind", "delta"}, "camera_reset": {"kind"},
    }
    if not isinstance(kind, str) or kind not in fields or set(value) != fields[kind]:
        raise ValueError("Unknown app input or fields")
    if kind == "key":
        if not isinstance(value["key"], str) or value["key"] not in ENVIRONMENT_KEYS:
            raise ValueError("Only documented environment controls are allowed; no direct fly steering")
    else:
        for field in fields[kind] - {"kind"}:
            number = value[field]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                raise ValueError("App coordinates must be finite numbers")
            limit = (0, 1) if kind == "pointer" else (-1, 1)
            if not limit[0] <= number <= limit[1]:
                raise ValueError("App coordinates are out of range")
    return value.copy()


def camera_input(camera, event, half_size_mm, model, data, unit_scale=1):
    import mujoco as mj
    import numpy as np

    kind = event["kind"]
    if kind == "camera_reset":
        camera.type = mj.mjtCamera.mjCAMERA_FREE
        camera.lookat[:] = [0, 0, 2*unit_scale]
        camera.distance = half_size_mm * 1.6
        camera.azimuth, camera.elevation = 135, -38
    elif kind == "orbit":
        camera.azimuth -= event["dx"] * 180
        camera.elevation = np.clip(camera.elevation - event["dy"] * 120, -89, -5)
    elif kind == "zoom":
        camera.distance = np.clip(camera.distance * math.exp(event["delta"]), 2*unit_scale, half_size_mm * 5)
    elif kind == "pan":
        scene = mj.MjvScene(model, maxgeom=10000)
        mj.mjv_updateScene(model, data, mj.MjvOption(), None, camera, mj.mjtCatBit.mjCAT_ALL, scene)
        optical = mj.mjv_averageCamera(scene.camera[0], scene.camera[1])
        right = np.cross(optical.forward, optical.up)
        camera.lookat[:] += camera.distance * (-event["dx"] * right + event["dy"] * optical.up)
    else:
        raise ValueError("Expected a camera input")
    camera.type = mj.mjtCamera.mjCAMERA_FREE
