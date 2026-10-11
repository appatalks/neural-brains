"""X11 pointer-to-arena finger and explicitly approximate looming features."""

import math
import os
import subprocess
from dataclasses import dataclass


def pointer_target(camera, viewport, x, y, plane_z=1.5):
    """Perspective ray intersects a horizontal arena plane; world units mm."""
    import numpy as np

    width, height = viewport.width, viewport.height
    if width <= 0 or height <= 0:
        return None
    u = (x - viewport.left) / width
    v = (y - viewport.bottom) / height
    if not 0 <= u <= 1 or not 0 <= v <= 1:
        return None
    position = np.asarray(camera.pos)
    forward = np.asarray(camera.forward)
    up = np.asarray(camera.up)
    right = np.cross(forward, up)
    near = camera.frustum_near
    if near <= 0:
        raise ValueError("Camera has invalid near plane")
    vertical = camera.frustum_bottom + v * (camera.frustum_top - camera.frustum_bottom)
    horizontal = getattr(camera, "frustum_center", 0.0) + (u - 0.5) * (
        camera.frustum_top - camera.frustum_bottom
    ) * width / height
    ray = forward * near + right * horizontal + up * vertical
    if abs(ray[2]) < 1e-8:
        return None
    distance = (plane_z - position[2]) / ray[2]
    if distance <= 0:
        return None
    return position + distance * ray


class Pointer:
    def __init__(self):
        windows = subprocess.check_output(
            ["xdotool", "search", "--all", "--sync", "--onlyvisible", "--pid", str(os.getpid()), "--name", "MuJoCo"],
            text=True, timeout=10,
        ).splitlines()
        if len(windows) != 1:
            raise RuntimeError("Expected exactly one native habitat window for virtual finger")
        self.window = windows[0]

    def window_viewport(self):
        import mujoco as mj
        text = subprocess.check_output(
            ["xdotool", "getwindowgeometry", "--shell", self.window],
            text=True, timeout=2,
        )
        values = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        return mj.MjrRect(0, 0, int(values["WIDTH"]), int(values["HEIGHT"]))

    def position(self, viewport=None):
        def values(command):
            text = subprocess.check_output(command, text=True, timeout=2)
            return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        pointer = values(["xdotool", "getmouselocation", "--shell"])
        bounds = values(["xdotool", "getwindowgeometry", "--shell", self.window])
        x, y = int(pointer["X"]) - int(bounds["X"]), int(pointer["Y"]) - int(bounds["Y"])
        if not 0 <= x < int(bounds["WIDTH"]) or not 0 <= y < int(bounds["HEIGHT"]):
            return None
        y = int(bounds["HEIGHT"]) - y
        if viewport is not None:
            # X11 uses logical window pixels; MuJoCo uses framebuffer pixels.
            x *= (viewport.left + viewport.width) / int(bounds["WIDTH"])
            y *= (viewport.bottom + viewport.height) / int(bounds["HEIGHT"])
        return x, y


@dataclass
class Looming:
    previous_angle: float | None = None

    def sample(self, distance_mm, radius_mm, duration_s, enabled):
        if duration_s <= 0 or distance_mm < 0 or radius_mm <= 0:
            raise ValueError("Invalid looming feature dimensions")
        angle = 2 * math.atan2(radius_mm, max(distance_mm, 0.001))
        velocity = 0 if self.previous_angle is None else (angle - self.previous_angle) / duration_s
        self.previous_angle = angle if enabled else None
        active = bool(enabled and angle >= 0.1 and velocity > 0.05)
        return {
            "angular_size_rad": angle, "angular_velocity_rad_s": velocity,
            "looming_active": active,
            "encoder": "engineering gate angle>=0.1 rad and expansion>0.05 rad/s; NOT fitted physiology",
        }
