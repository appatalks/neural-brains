"""Geometric spherical looming features; not fitted neural response curves."""

import math
from dataclasses import dataclass


GRADED_ENCODER = {
    "scope": "Assumed continuous looming drive: LC4 expansion velocity, LPLC2 size with expansion gain. Not fitted physiology, full retinal encoding or a natural DNp10 landing pathway.",
    "maximum_rate_Hz": 100.0,
    "lc4_velocity_half_rad_s": .1,
    "lplc2_size_half_rad": .05,
    "lplc2_expansion_half_rad_s": .05,
    "binocular_pooling": "maximum per-population drive across visible spheres and eyes; no side-specific receptive-field mapping",
}


def validate_visual_rates(rates):
    if not isinstance(rates, dict) or set(rates) != {"LC4", "LPLC2"}:
        raise ValueError("Visual rates require exactly LC4 and LPLC2")
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or not 0 <= value <= GRADED_ENCODER["maximum_rate_Hz"] for value in rates.values()):
        raise ValueError("Visual rates must be finite numbers in [0, 100] Hz")
    return {key: float(rates[key]) for key in ("LC4", "LPLC2")}


def graded_visual_rates(features):
    if not isinstance(features, list) or not features:
        raise ValueError("Graded encoder requires explicit eye samples")
    rates = {"LC4": 0., "LPLC2": 0.}
    for feature in features:
        visible = feature["visible"]
        angle, velocity = feature["angular_size_rad"], feature["angular_velocity_rad_s"]
        if (type(visible) is not bool or type(angle) not in (int, float)
            or type(velocity) not in (int, float) or not math.isfinite(angle)
            or not math.isfinite(velocity) or not 0 <= angle <= math.pi):
            raise ValueError("Graded encoder requires finite angular geometry and explicit visibility")
        if not visible or velocity <= 0:
            continue
        lc4 = 100 * velocity / (velocity + GRADED_ENCODER["lc4_velocity_half_rad_s"])
        lplc2 = (100 * angle / (angle + GRADED_ENCODER["lplc2_size_half_rad"])
                 * velocity / (velocity + GRADED_ENCODER["lplc2_expansion_half_rad_s"]))
        rates["LC4"] = max(rates["LC4"], lc4)
        rates["LPLC2"] = max(rates["LPLC2"], lplc2)
    return validate_visual_rates(rates)


def angular_diameter(distance, radius):
    if not math.isfinite(distance) or not math.isfinite(radius) or distance < 0 or radius <= 0:
        raise ValueError("Sphere distance/radius must be finite and physically valid")
    return math.pi if distance <= radius else 2 * math.asin(radius / distance)


def field_visible(direction, forward, fovy_deg, angular_size):
    if (
        len(direction) != 3 or len(forward) != 3
        or any(not math.isfinite(value) for value in list(direction) + list(forward))
        or not math.isfinite(fovy_deg) or not math.isfinite(angular_size)
        or not 0 <= angular_size <= math.pi
    ):
        raise ValueError("Camera field geometry must be finite 3D vectors and angles")
    norm = math.sqrt(sum(x*x for x in direction))
    forward_norm = math.sqrt(sum(x*x for x in forward))
    if not norm or not forward_norm or not 0 < fovy_deg < 180:
        raise ValueError("Invalid camera direction or field of view")
    cosine = sum(a*b for a, b in zip(direction, forward)) / (norm * forward_norm)
    angle = math.acos(max(-1, min(1, cosine)))
    return angle <= math.radians(fovy_deg) / 2 + angular_size / 2


@dataclass
class SphereLooming:
    previous_angle: float | None = None

    def sample(self, distance_mm, radius_mm, duration_s, enabled, visible=True):
        if not math.isfinite(duration_s) or duration_s <= 0:
            raise ValueError("Looming interval must be positive and finite")
        if type(enabled) is not bool or type(visible) is not bool:
            raise ValueError("Visibility/enabled state must be explicit booleans")
        angle = angular_diameter(distance_mm, radius_mm)
        velocity = 0 if self.previous_angle is None else (angle - self.previous_angle) / duration_s
        observable = bool(enabled and visible)
        self.previous_angle = angle if observable else None
        return {
            "angular_size_rad": angle,
            "angular_velocity_rad_s": velocity if observable else 0,
            "visible": observable,
            "looming_active": bool(observable and velocity > 0.05 and angle >= 0.1),
            "geometry": "spherical silhouette: 2*asin(radius/distance)",
            "encoder": "uncalibrated engineering gate; not fitted LC4/LPLC2 response curves",
        }


class SphereVision:
    """Bounded source/eye histories sampled only on advancing physical intervals."""

    def __init__(self):
        self.states = {}

    def reset(self):
        self.states.clear()

    def forget(self, geom_id):
        self.states = {key: state for key, state in self.states.items() if key[0] != geom_id}

    def sample(self, model, data, sources, eye_ids, body_id, duration_s):
        if not isinstance(sources, list) or len(sources) > 512 or len(eye_ids) != 2:
            raise ValueError("Sphere vision requires at most 512 sources and two eyes")
        ids = [source["geom_id"] for source in sources]
        if len(set(ids)) != len(ids) or len(set(eye_ids)) != 2:
            raise ValueError("Sphere vision source and eye identities must be unique")
        present = {(source, eye) for source in ids for eye in eye_ids}
        self.states = {key: state for key, state in self.states.items() if key in present}
        features = []
        for source in sources:
            geom = source["geom_id"]
            if not 0 <= geom < model.ngeom or int(model.geom_type[geom]) != 2:
                raise ValueError("Sphere vision requires compiled spherical geometry")
            position = data.geom_xpos[geom]
            radius = float(model.geom_size[geom, 0])
            views = finger_visibility(model, data, geom, position, radius, eye_ids, body_id)
            for view in views:
                key = (geom, view["camera_id"])
                state = self.states.setdefault(key, SphereLooming())
                feature = state.sample(view["distance_mm"]*10, radius*10, duration_s,
                                       source["enabled"], view["visible"])
                features.append({**feature, "source_name": source["name"],
                                 "camera_id": view["camera_id"], "occluded": view["occluded"]})
        if not features:
            features = [{"visible": False, "angular_size_rad": 0., "angular_velocity_rad_s": 0.}]
        return features


class LandingSurfaceVision:
    """Explicit bounding-sphere approximation of visible surface expansion."""

    def __init__(self):
        self.states={}

    def reset(self):
        self.states.clear()

    def sample(self,model,data,geom_ids,eye_ids,body_id,duration_s,flying):
        features=[]
        for geom in geom_ids:
            radius=float(model.geom_rbound[geom])
            if radius<=0:
                raise ValueError("Landing surface requires bounded physical geometry")
            views=finger_visibility(model,data,geom,data.geom_xpos[geom],radius,eye_ids,body_id)
            for view in views:
                state=self.states.setdefault((geom,view["camera_id"]),SphereLooming())
                feature=state.sample(view["distance_mm"]*10,radius*10,duration_s,
                                     flying,view["visible"])
                features.append({**feature,"surface_geom_id":int(geom),"camera_id":view["camera_id"],
                                 "encoder":"Assumed landing-surface bounding silhouette through existing LC4/LPLC2 model input; not calibrated natural DNp10 visual pathway"})
        return features


def finger_visibility(model, data, finger_geom_id, position, radius, eye_ids, body_id):
    import mujoco as mj
    import numpy as np

    views = []
    for eye in eye_ids:
        origin = data.cam_xpos[eye]
        forward = -data.cam_xmat[eye].reshape(3, 3)[:, 2]
        direction = np.asarray(position) - origin
        distance = float(np.linalg.norm(direction))
        angle = angular_diameter(distance, radius)
        in_field = distance <= radius or field_visible(direction, forward, float(model.cam_fovy[eye]), angle)
        hit = np.zeros(1, dtype=np.int32)
        obstructed = False
        if distance > radius and in_field:
            ray_distance = mj.mj_ray(
                model, data, origin, direction / distance,
                np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8),
                True, body_id, hit,
            )
            obstructed = ray_distance >= 0 and hit[0] != finger_geom_id and ray_distance < distance - radius
        views.append({
            "camera_id": int(eye), "distance_mm": distance,
            "angular_size_rad": angle, "in_field": bool(in_field), "occluded": bool(obstructed),
            "visible": bool(in_field and not obstructed),
        })
    return views
