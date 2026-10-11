"""Explicit environment approximations and walking sensor/motor contracts."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


def number(value, label: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return float(value)


def vector(values, label: str, length: int = 3) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)) or len(values) != length:
        raise ValueError(f"{label} must contain {length} numbers")
    return tuple(number(value, label) for value in values)


@dataclass(frozen=True)
class Source:
    name: str
    position_mm: tuple[float, ...]
    strength: float
    spread_mm: float

    def value_at(self, position) -> float:
        squared = sum((a - b) ** 2 for a, b in zip(self.position_mm, position))
        return self.strength * math.exp(-squared / (2 * self.spread_mm ** 2))


@dataclass(frozen=True)
class Terrain:
    name: str
    position_mm: tuple[float, ...]
    half_size_mm: tuple[float, ...]
    pitch_rad: float
    friction: tuple[float, ...]


@dataclass(frozen=True)
class Material:
    name: str
    rgba: tuple[float, ...]
    friction: tuple[float, ...]
    specular: float
    shininess: float


@dataclass(frozen=True)
class HabitatObject:
    name: str
    kind: str
    position_mm: tuple[float, ...]
    size_mm: tuple[float, ...]
    pitch_rad: float
    material: str


@dataclass(frozen=True)
class MovableObject(HabitatObject):
    mass_mg: float


@dataclass(frozen=True)
class Environment:
    half_size_mm: float
    walls_height_mm: float
    ground_friction: tuple[float, ...]
    terrain: tuple[Terrain, ...]
    odors: tuple[Source, ...]
    lights: tuple[Source, ...]
    wind_mm_s: tuple[float, ...]
    drag_uN_per_mm_s: float
    drag_limit_uN: float
    range_limit_mm: float
    schema_version: int = 1
    materials: tuple[Material, ...] = ()
    objects: tuple[HabitatObject, ...] = ()
    ground_material: str | None = None
    movable_objects: tuple[MovableObject, ...] = ()

    @classmethod
    def load(cls, path: Path):
        data = json.loads(path.read_text())
        fields = {
            "schema_version", "half_size_mm", "walls_height_mm", "ground_friction",
            "terrain", "odors", "lights", "wind_mm_s", "drag_uN_per_mm_s",
            "drag_limit_uN", "range_limit_mm",
        }
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] not in {1, 2, 3}:
            raise ValueError("Environment requires documented schema version 1, 2 or 3")
        version = data["schema_version"]
        expected = fields if version == 1 else fields | {"materials", "objects"}
        if version == 3:
            expected |= {"ground_material", "movable_objects"}
        if set(data) != expected:
            raise ValueError("Environment must contain exactly the documented schema fields")
        names = set()

        def name(entry):
            value = entry["name"]
            reserved = {
                "ground_plane", "groundplane", "virtual_finger", "virtual_finger_tip",
                "virtual_finger_shaft", "finger_tip", "finger_shaft", "pointer_target",
                "sugar_exposure_region", "mn9_readout_marker",
            }
            if (
                not isinstance(value, str) or not value.isidentifier() or value in names
                or value in reserved or value.startswith(("arena_wall_", "source_light_", "editable_"))
            ):
                raise ValueError("Environment names must be unique identifiers")
            names.add(value)
            return value

        def sources(entries):
            result = []
            if not isinstance(entries, list):
                raise ValueError("Sources must be a list")
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {"name", "position_mm", "strength", "spread_mm"}:
                    raise ValueError("Invalid odor/light source fields")
                result.append(Source(
                    name(entry), vector(entry["position_mm"], "source position"),
                    number(entry["strength"], "strength", 0),
                    number(entry["spread_mm"], "spread_mm", 0.001),
                ))
            return tuple(result)

        half = number(data["half_size_mm"], "half_size_mm", 5)
        if not isinstance(data["terrain"], list):
            raise ValueError("Terrain must be a list")
        terrain = []
        for entry in data["terrain"]:
            if not isinstance(entry, dict) or set(entry) != {"name", "position_mm", "half_size_mm", "pitch_rad", "friction"}:
                raise ValueError("Invalid terrain fields")
            position = vector(entry["position_mm"], "terrain position")
            size = vector(entry["half_size_mm"], "terrain size")
            if any(value <= 0 for value in size):
                raise ValueError("Terrain half sizes must be positive")
            pitch = number(entry["pitch_rad"], "pitch_rad")
            x_extent = abs(math.cos(pitch)) * size[0] + abs(math.sin(pitch)) * size[2]
            if abs(position[0]) + x_extent >= half or abs(position[1]) + size[1] >= half:
                raise ValueError("Terrain must fit inside arena bounds")
            friction = vector(entry["friction"], "terrain friction")
            if any(value < 0 for value in friction):
                raise ValueError("Friction coefficients cannot be negative")
            terrain.append(Terrain(
                name(entry), position, size, pitch, friction,
            ))
        friction = vector(data["ground_friction"], "ground_friction")
        if any(value < 0 for value in friction):
            raise ValueError("Friction coefficients cannot be negative")
        materials = []
        objects = []
        movable = []
        ground_material = None
        if version >= 2:
            if not isinstance(data["materials"], list) or not isinstance(data["objects"], list):
                raise ValueError("Materials and objects must be lists")
            if len(data["materials"]) > 32 or len(data["objects"]) > 256:
                raise ValueError("Habitat supports at most 32 materials and 256 static objects")
            for entry in data["materials"]:
                if not isinstance(entry, dict) or set(entry) != {"name", "rgba", "friction", "specular", "shininess"}:
                    raise ValueError("Invalid material fields")
                rgba = vector(entry["rgba"], "material rgba", 4)
                surface = vector(entry["friction"], "material friction")
                specular = number(entry["specular"], "specular", 0)
                shininess = number(entry["shininess"], "shininess", 0)
                if any(not 0 <= value <= 1 for value in rgba) or any(value < 0 for value in surface) or max(specular, shininess) > 1:
                    raise ValueError("Material colors/specularity must be in [0, 1] and friction nonnegative")
                materials.append(Material(name(entry), rgba, surface, specular, shininess))
            by_name = {material.name: material for material in materials}
            movable_entries = data["movable_objects"] if version == 3 else []
            if not isinstance(movable_entries, list) or len(movable_entries) > 32:
                raise ValueError("Habitat supports at most 32 movable objects")
            if version == 3:
                ground_material = data["ground_material"]
                if not isinstance(ground_material, str) or ground_material not in by_name:
                    raise ValueError("Ground material must reference a declared material")
            for entry, dynamic in [(e, False) for e in data["objects"]] + [(e, True) for e in movable_entries]:
                fields = {"name", "kind", "position_mm", "size_mm", "pitch_rad", "material"}
                if dynamic:
                    fields |= {"mass_mg"}
                if not isinstance(entry, dict) or set(entry) != fields:
                    raise ValueError("Invalid habitat object fields")
                kind = entry["kind"]
                if not isinstance(kind, str) or kind not in {"box", "ellipsoid", "sphere", "capsule"}:
                    raise ValueError("Unsupported static habitat object shape")
                size = vector(entry["size_mm"], "object size", {"sphere": 1, "capsule": 2}.get(kind, 3))
                position = vector(entry["position_mm"], "object position")
                pitch = number(entry["pitch_rad"], "object pitch")
                if any(value <= 0 for value in size):
                    raise ValueError("Object sizes must be positive")
                if not isinstance(entry["material"], str) or entry["material"] not in by_name:
                    raise ValueError("Object material must reference a declared material")
                if kind == "sphere":
                    extent = (size[0],) * 3
                elif kind == "capsule":
                    extent = (abs(math.sin(pitch))*size[1]+size[0], size[0], abs(math.cos(pitch))*size[1]+size[0])
                elif kind == "ellipsoid":
                    extent = (
                        math.hypot(math.cos(pitch)*size[0], math.sin(pitch)*size[2]),
                        size[1], math.hypot(math.sin(pitch)*size[0], math.cos(pitch)*size[2]),
                    )
                else:
                    extent = (abs(math.cos(pitch))*size[0]+abs(math.sin(pitch))*size[2],
                              size[1], abs(math.sin(pitch))*size[0]+abs(math.cos(pitch))*size[2])
                if abs(position[0])+extent[0] >= half or abs(position[1])+extent[1] >= half or position[2]-extent[2] < -1e-6:
                    raise ValueError("Objects must fit inside arena XY bounds and above the ground")
                if dynamic:
                    mass = number(entry["mass_mg"], "movable mass_mg", 0.001)
                    if mass > 1000:
                        raise ValueError("Movable objects must have mass <=1000 mg")
                    movable.append(MovableObject(name(entry), kind, position, size, pitch, entry["material"], mass))
                else:
                    objects.append(HabitatObject(name(entry), kind, position, size, pitch, entry["material"]))
        return cls(
            half, number(data["walls_height_mm"], "walls_height_mm", 0), friction,
            tuple(terrain), sources(data["odors"]), sources(data["lights"]),
            vector(data["wind_mm_s"], "wind_mm_s"),
            number(data["drag_uN_per_mm_s"], "drag_uN_per_mm_s", 0),
            number(data["drag_limit_uN"], "drag_limit_uN", 0),
            number(data["range_limit_mm"], "range_limit_mm", 0.1),
            version, tuple(materials), tuple(objects), ground_material, tuple(movable),
        )

    def wind_force(self, velocity) -> tuple[float, ...]:
        force = [(wind - speed) * self.drag_uN_per_mm_s for wind, speed in zip(self.wind_mm_s, velocity)]
        norm = math.sqrt(sum(value * value for value in force))
        scale = min(1.0, self.drag_limit_uN / norm) if norm else 1.0
        return tuple(value * scale for value in force)


def object_definitions(environment: Environment, scale: float = 1, objects=None) -> list[dict]:
    materials = {material.name: material for material in environment.materials}
    return [{
        "name": obj.name, "type": obj.kind,
        "pos": [value*scale for value in obj.position_mm],
        "size": [value*scale for value in obj.size_mm],
        "quat": [math.cos(obj.pitch_rad/2), 0, math.sin(obj.pitch_rad/2), 0],
        "material": obj.material, "friction": list(materials[obj.material].friction),
        "group": 0, "contype": 1, "conaffinity": 1,
    } for obj in (environment.objects if objects is None else objects)]


@dataclass(frozen=True)
class MotorCommand:
    left_drive: float
    right_drive: float
    mode: str = "walk"

    def __post_init__(self):
        if self.mode != "walk":
            raise ValueError("Only walking is supported; aerodynamic flight is not connected")
        for value in (self.left_drive, self.right_drive):
            if not 0 <= number(value, "motor drive") <= 1.5:
                raise ValueError("Motor drive must be between 0 and 1.5")


@dataclass(frozen=True)
class Observation:
    time_s: float
    episode: int
    position_mm: tuple[float, ...]
    velocity_mm_s: tuple[float, ...]
    odor_left: float
    odor_right: float
    light_left: float
    light_right: float
    range_left_mm: float
    range_forward_mm: float
    range_right_mm: float
    joint_angles_rad: tuple[float, ...]
    joint_velocities_rad_s: tuple[float, ...]
    contacts: int
    uprightness: float = 1.0
    visual_activity_left: float | None = None
    visual_activity_right: float | None = None


def sensory_command(observation: Observation, base_drive: float) -> MotorCommand:
    """A transparent engineered baseline, not a biological/connectomic policy."""
    number(base_drive, "base_drive", 0)
    if observation.uprightness < 0.25:
        return MotorCommand(0, 0)
    gradient = observation.odor_left - observation.odor_right
    odor_turn = max(-0.3, min(0.3, gradient))
    visual_turn = 0.0
    if observation.visual_activity_left is not None or observation.visual_activity_right is not None:
        left = number(observation.visual_activity_left, "left retinal activity", 0)
        right = number(observation.visual_activity_right, "right retinal activity", 0)
        if left > 1 or right > 1:
            raise ValueError("Normalized retinal activity cannot exceed 1")
        visual_turn = 0.2 * (left - right) / max(left + right, 0.001)
    clearance = min(observation.range_left_mm, observation.range_forward_mm, observation.range_right_mm)
    if observation.range_forward_mm < 5.0 or clearance < 1.5:
        avoidance = 0.8 if observation.range_left_mm >= observation.range_right_mm else -0.8
    else:
        avoidance = 0.0
    turn = odor_turn + visual_turn + avoidance
    drive = min(base_drive, 0.4) if avoidance else base_drive
    # Differential command: left turn means stronger right-side gait.
    return MotorCommand(
        max(0.0, min(1.5, drive - turn)),
        max(0.0, min(1.5, drive + turn)),
    )


def sample_environment(sim, fly, body_id: int, environment: Environment, time_s: float, episode: int) -> Observation:
    import mujoco as mj
    import numpy as np

    position = sim.mj_data.xpos[body_id].copy()
    rotation = sim.mj_data.xmat[body_id].reshape(3, 3)
    center = position + rotation @ np.array([0.6, 0.0, 0.0])
    left = center + rotation @ np.array([0, 0.25, 0])
    right = center + rotation @ np.array([0, -0.25, 0])
    rays = []
    for angle in [math.pi / 4, 0, -math.pi / 4]:
        direction = rotation @ np.array([math.cos(angle), math.sin(angle), 0])
        hit = np.zeros(1, dtype=np.int32)
        distance = mj.mj_ray(
            sim.mj_model, sim.mj_data, center, direction,
            np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, body_id, hit,
        )
        rays.append(environment.range_limit_mm if distance < 0 else min(distance, environment.range_limit_mm))
    velocity = np.zeros(6)
    mj.mj_objectVelocity(sim.mj_model, sim.mj_data, mj.mjtObj.mjOBJ_BODY, body_id, velocity, False)
    return Observation(
        time_s, episode, tuple(position.tolist()), tuple(velocity[3:].tolist()),
        sum(source.value_at(left) for source in environment.odors),
        sum(source.value_at(right) for source in environment.odors),
        sum(source.value_at(left) for source in environment.lights),
        sum(source.value_at(right) for source in environment.lights),
        *rays,
        tuple(sim.get_joint_angles(fly.name).tolist()),
        tuple(sim.get_joint_velocities(fly.name).tolist()), sim.mj_data.ncon,
        float(rotation[2, 2]),
    )


def load_schedule(path: Path | None) -> list[dict]:
    if path is None:
        return []
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise ValueError("Interaction schedule must be a list")
    previous = -1.0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"time_s", "key"}:
            raise ValueError("Schedule entries need time_s and key")
        timestamp = number(entry["time_s"], "schedule time", 0)
        if timestamp < previous:
            raise ValueError("Schedule must be sorted by time_s")
        previous = timestamp
        if entry["key"] not in list("WSADXOFBRNT[]"):
            raise ValueError("Unsupported scheduled key; pause is interactive-only")
    return entries


def environment_dict(environment: Environment) -> dict:
    result = asdict(environment)
    if environment.schema_version == 1:
        result.pop("materials")
        result.pop("objects")
    if environment.schema_version < 3:
        result.pop("ground_material")
        result.pop("movable_objects")
    return result
