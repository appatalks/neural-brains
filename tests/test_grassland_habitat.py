import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from fly_environment import Environment, environment_dict
from fly_feeding import FeedingConfig
from fly_flight_arena import make_arena, FlyContactReader
from fly_flight_avoidance import FlightAvoidance
from sim_units import FLIGHT_UNITS


class GrasslandTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/"experiments/fly-walking/grassland-habitat.json"
        self.raw=json.loads(self.path.read_text())
        self.scene=Environment.load(self.path)

    def load(self,raw):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"scene.json"
            path.write_text(json.dumps(raw))
            return Environment.load(path)

    def test_exact_quarter_dimension_reduction_and_versioned_roundtrip(self):
        self.assertEqual(self.scene.half_size_mm,150*.75)
        self.assertEqual(2*self.scene.half_size_mm,225)
        self.assertEqual(self.load(environment_dict(self.scene)),self.scene)
        for filename in ("habitat.json","planted-habitat.json"):
            legacy=Environment.load(ROOT/"experiments/fly-walking"/filename)
            self.assertNotIn("movable_objects",environment_dict(legacy))
            self.assertNotIn("ground_material",environment_dict(legacy))
        self.assertEqual(len([obj for obj in self.scene.objects if obj.name.startswith("grass_")]),48)
        self.assertEqual(len(self.scene.materials),14)
        self.assertEqual(len(self.scene.movable_objects),3)

    def test_invalid_masses_materials_fields_and_bounds_fail(self):
        for changes in ({"mass_mg":0},{"mass_mg":True},{"mass_mg":1001},{"mass_mg":float("nan")},
                        {"position_mm":[112.4,0,1]},{"material":"missing"},{"extra":1}):
            raw=copy.deepcopy(self.raw)
            raw["movable_objects"][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.load(raw)
        raw=copy.deepcopy(self.raw)
        raw["ground_material"]="missing"
        with self.assertRaises(ValueError):
            self.load(raw)
        raw=copy.deepcopy(self.raw)
        raw["movable_objects"][0]["name"]=raw["objects"][0]["name"]
        with self.assertRaises(ValueError):
            self.load(raw)

    def test_food_alignment_and_clear_walk_route(self):
        food=FeedingConfig.load(ROOT/"experiments/flywire-sugar/grassland-feeding.json")
        fruit=next(obj for obj in self.scene.objects if obj.name=="fruit_food_surface")
        odor=next(source for source in self.scene.odors if source.name=="fruit_odor_proxy")
        self.assertEqual(fruit.position_mm[:2],food.position_mm[:2])
        self.assertEqual(odor.position_mm,food.position_mm)
        self.assertGreater(fruit.position_mm[1]-fruit.size_mm[1],1.5)
        self.assertTrue(food.exposure([9,4,1])["sugar_contact"])
        self.assertFalse(food.exposure([9,4,1],False)["sugar_contact"])

    def test_compact_turn_limits_scale_without_changing_legacy(self):
        small=FlightAvoidance(11.25)
        old=FlightAvoidance(15)
        self.assertEqual(small.maximum_turn,3.)
        self.assertEqual(small.maximum_turn_acceleration,12.)
        self.assertEqual(small.speed,15.)
        self.assertEqual(old.speed,20.)
        self.assertEqual(old.maximum_turn,3.)
        self.assertEqual(old.maximum_turn_acceleration,12.)
        small.begin([0,0,1],0)
        for step in range(30):
            small.update([0,0,1],step*.01,[])
        self.assertLessEqual(abs(small.turn_rate),3.)

    def test_unsupported_walking_backend_fails_explicitly(self):
        from fly_walking import build_scene
        with self.assertRaisesRegex(ValueError,"unified FlyBody"):
            build_scene(self.scene)

    @unittest.skipUnless(importlib.util.find_spec("dm_control"),"Pinned FlyBody environment required")
    def test_compiled_free_body_mass_collision_and_ground_texture(self):
        import numpy as np
        from dm_control import mjcf
        arena=make_arena(self.scene)
        physics=mjcf.Physics.from_mjcf_model(arena.mjcf_model)
        try:
            model=physics.model
            ground=model.name2id("groundplane","geom")
            material=model.geom_matid[ground]
            self.assertEqual(model.id2name(material,"material"),"soil_material")
            self.assertTrue((np.asarray(model.mat_texid[material])>=0).any())
            for obj in self.scene.movable_objects:
                body=model.name2id(obj.name+"_body","body")
                geom=model.name2id(obj.name,"geom")
                self.assertAlmostEqual(model.body_mass[body],FLIGHT_UNITS.mass_from_mg(obj.mass_mg))
                self.assertGreater(model.geom_contype[geom],0)
                self.assertGreater(model.geom_conaffinity[geom],0)
                self.assertEqual(model.body_jntnum[body],1)
                joint=model.name2id(obj.name+"_joint","joint")
                self.assertEqual(model.jnt_type[joint],0)
        finally:
            physics.free()

    @unittest.skipUnless(importlib.util.find_spec("dm_control"),"Pinned FlyBody environment required")
    def test_loose_object_floor_contacts_are_not_fly_landing(self):
        from fly_unified import create_environment
        with create_environment(self.scene,.2) as env:
            env.reset()
            env.task.walker.set_pose(env.physics,[0,0,3])
            env.physics.forward()
            model,data=env.physics.model.ptr,env.physics.data.ptr
            reader=FlyContactReader(model,self.scene)
            for _ in range(600):
                env.physics.step()
            self.assertGreater(data.ncon,0)
            self.assertEqual(reader.sample(data),0)
            self.assertTrue(all(obj["fly_contact_steps"]==0 for obj in reader.movable_snapshot(data)))
            self.assertEqual(len(reader.movable_snapshot(data)),3)

    @unittest.skipUnless(importlib.util.find_spec("mujoco"),"MuJoCo required for flight obstacle memory")
    def test_low_grass_does_not_exhaust_flight_obstacle_memory(self):
        import mujoco as mj
        from fly_flight_avoidance import obstacle_samples
        grass="".join(f'<geom name="blade_{i}" type="sphere" pos="{i*.1} 2 .2" size=".1"/>'
                      for i in range(40))
        model=mj.MjModel.from_xml_string(
            '<mujoco><worldbody><body name="fly" pos="0 0 1"><freejoint/>'
            '<geom name="fly_geom" type="sphere" size=".05"/></body>'
            +grass+'<geom name="flight_obstacle" type="sphere" pos="3 0 1" size=".2"/>'
            '</worldbody></mujoco>')
        data=mj.MjData(model)
        mj.mj_forward(model,data)
        remembered=[model.geom(f"blade_{i}").id for i in range(40)]+[model.geom("flight_obstacle").id]
        samples=obstacle_samples(model,data,model.body("fly").id,remembered)
        self.assertEqual([item["geom_id"] for item in samples],[model.geom("flight_obstacle").id])
