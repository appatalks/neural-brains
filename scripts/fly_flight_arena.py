"""Adapt the shared millimeter habitat to FlyBody's centimeter physics."""

import math

from fly_environment import Environment, object_definitions
from sim_units import FLIGHT_UNITS


def geometry_definitions(environment: Environment) -> list[dict]:
    convert = FLIGHT_UNITS.length_from_mm
    definitions = object_definitions(environment, convert(1))
    for terrain in environment.terrain:
        definitions.append({
            "name": terrain.name, "type": "box",
            "pos": [convert(value) for value in terrain.position_mm],
            "size": [convert(value) for value in terrain.half_size_mm],
            "quat": [math.cos(terrain.pitch_rad / 2), 0, math.sin(terrain.pitch_rad / 2), 0],
            "friction": list(terrain.friction), "rgba": [0.8, 0.45, 0.15, 1],
            "group": 0, "contype": 1, "conaffinity": 1,
        })
    half = environment.half_size_mm
    height = environment.walls_height_mm
    if height:
        for index, (position, size) in enumerate([
            ([half, 0, height / 2], [0.25, half, height / 2]),
            ([-half, 0, height / 2], [0.25, half, height / 2]),
            ([0, half, height / 2], [half, 0.25, height / 2]),
            ([0, -half, height / 2], [half, 0.25, height / 2]),
        ]):
            definitions.append({
                "name": f"arena_wall_{index}", "type": "box",
                "pos": [convert(value) for value in position],
                "size": [convert(value) for value in size],
                "rgba": [0.3, 0.45, 0.5, 0.35],
                "group": 0, "contype": 1, "conaffinity": 1,
            })
    for sources, color in [
        (environment.odors, [0.1, 0.8, 0.2, 1]),
        (environment.lights, [1, 1, 0.2, 1]),
    ]:
        for source in sources:
            definitions.append({
                "name": source.name, "type": "sphere",
                "pos": [convert(value) for value in source.position_mm],
                "size": [convert(0.3)], "rgba": color,
                "group": 2, "contype": 0, "conaffinity": 0,
            })
    names = [definition["name"] for definition in definitions]
    if len(names) != len(set(names)) or "groundplane" in names:
        raise ValueError("Habitat names collide with reserved flight arena geometry")
    return definitions


def make_arena(environment: Environment):
    from dm_control.locomotion.arenas import floors

    half = FLIGHT_UNITS.length_from_mm(environment.half_size_mm)
    arena = floors.Floor(size=(half, half))
    root = arena.mjcf_model
    ground = root.find("geom", "groundplane")
    ground.friction = environment.ground_friction
    if environment.ground_material:
        root.asset.add("texture", name="habitat_soil_texture", type="2d", builtin="flat",
                       width=512, height=512, rgb1=[.22,.14,.065], rgb2=[.29,.2,.1],
                       mark="random", markrgb=[.38,.28,.15], random=.15)
    for material in environment.materials:
        definition = dict(
            name=material.name, rgba=material.rgba,
            specular=material.specular, shininess=material.shininess,
        )
        if material.name == environment.ground_material:
            definition.update(texture="habitat_soil_texture", texrepeat=[30,30], texuniform=True)
        root.asset.add("material", **definition)
    if environment.ground_material:
        ground.material = environment.ground_material
        root.worldbody.add("light", name="habitat_daylight", pos=[0,0,20], dir=[-.3,-.4,-1],
                           directional=True, diffuse=[.8,.78,.7], ambient=[.25,.27,.22],
                           specular=[.1,.1,.1], castshadow=True)
    for definition in geometry_definitions(environment):
        root.worldbody.add("geom", **definition)
    for obj, definition in zip(environment.movable_objects,
                               object_definitions(environment, FLIGHT_UNITS.length_from_mm(1), environment.movable_objects)):
        body = root.worldbody.add("body", name=obj.name+"_body",
                                 pos=definition.pop("pos"), quat=definition.pop("quat"))
        body.add("freejoint", name=obj.name+"_joint")
        body.add("geom", **definition, mass=FLIGHT_UNITS.mass_from_mg(obj.mass_mg))
    for index, source in enumerate(environment.lights):
        root.worldbody.add(
            "light", name=f"source_light_{index}",
            pos=[FLIGHT_UNITS.length_from_mm(value) for value in source.position_mm],
            dir=[0, 0, -1], diffuse=[min(source.strength, 1)] * 3,
        )
    return arena


class FlyContactReader:
    """Separate fly contacts from loose-object/floor contacts in one physical world."""

    def __init__(self, model, environment):
        import mujoco as mj

        self.model = model
        self.fly_geoms = {
            geom for geom in range(model.ngeom)
            if (mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom) or "").startswith("walker/")
        }
        if not self.fly_geoms:
            raise ValueError("Contact reader requires the compiled FlyBody geometry")
        self.ground = model.geom("groundplane").id
        self.movable = {model.geom(obj.name).id: obj for obj in environment.movable_objects}
        self.contact_steps = {geom: 0 for geom in self.movable}

    def sample(self, data):
        floor = 0
        touched = set()
        for contact in data.contact[:data.ncon]:
            a, b = contact.geom1, contact.geom2
            if a in self.fly_geoms:
                partner = b
            elif b in self.fly_geoms:
                partner = a
            else:
                continue
            floor += int(partner == self.ground)
            if partner in self.movable:
                touched.add(partner)
        for geom in touched:
            self.contact_steps[geom] += 1
        return floor

    def movable_snapshot(self, data):
        import mujoco as mj
        import numpy as np

        snapshots = []
        for geom, obj in self.movable.items():
            velocity = np.zeros(6)
            mj.mj_objectVelocity(self.model, data, mj.mjtObj.mjOBJ_BODY,
                                 int(self.model.geom_bodyid[geom]), velocity, False)
            snapshots.append({
                "name": obj.name, "mass_mg": obj.mass_mg,
                "position_mm": (data.geom_xpos[geom]*10).tolist(),
                "velocity_mm_s": (velocity[3:]*10).tolist(),
                "fly_contact_steps": self.contact_steps[geom],
                "scope": "Physical free-body contact; mass and friction are explicit assumptions, not measured biological response",
            })
        return snapshots


def sample_habitat(model, data, body_id: int, environment: Environment) -> dict:
    import mujoco as mj
    import numpy as np

    position_mm = np.asarray([
        FLIGHT_UNITS.length_to_mm(value) for value in data.xpos[body_id]
    ])
    rotation = data.xmat[body_id].reshape(3, 3)
    center_mm = position_mm + rotation @ np.array([0.6, 0, 0])
    left = center_mm + rotation @ np.array([0, 0.25, 0])
    right = center_mm + rotation @ np.array([0, -0.25, 0])
    ranges = []
    for angle in [math.pi / 4, 0, -math.pi / 4]:
        direction = rotation @ np.array([math.cos(angle), math.sin(angle), 0])
        hit = np.zeros(1, dtype=np.int32)
        distance = mj.mj_ray(
            model, data, np.asarray([
                FLIGHT_UNITS.length_from_mm(value) for value in center_mm
            ]), direction,
            np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, body_id, hit,
        )
        ranges.append(
            environment.range_limit_mm if distance < 0 else
            min(FLIGHT_UNITS.length_to_mm(distance), environment.range_limit_mm)
        )
    return {
        "position_mm": position_mm.tolist(),
        "outside_xy_bounds": any(abs(value) > environment.half_size_mm for value in position_mm[:2]),
        "odor_left": sum(source.value_at(left) for source in environment.odors),
        "odor_right": sum(source.value_at(right) for source in environment.odors),
        "light_left": sum(source.value_at(left) for source in environment.lights),
        "light_right": sum(source.value_at(right) for source in environment.lights),
        "range_left_mm": ranges[0], "range_forward_mm": ranges[1], "range_right_mm": ranges[2],
    }
