import math
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_looming import angular_diameter, field_visible, finger_visibility, SphereLooming, SphereVision, LandingSurfaceVision, graded_visual_rates
from electrical_synapses import GapJunction, currents_nA


class LoomingGeometryTests(unittest.TestCase):
    def test_landing_surface_uses_physical_expansion_and_no_nonflight_drive(self):
        try:
            import mujoco as mj
        except ModuleNotFoundError as error:
            if error.name!="mujoco":
                raise
            self.skipTest("MuJoCo required for surface expansion")
        model=mj.MjModel.from_xml_string("""
          <mujoco><worldbody><body name="fly"><camera name="left" fovy="90"/>
          <camera name="right" pos=".02 0 0" fovy="90"/></body>
          <geom name="surface" type="box" pos="0 0 -10" size="1 1 .1"/>
          <geom name="blocker" type="box" pos="5 0 -5" size="1 1 .1"/>
          </worldbody></mujoco>
        """)
        data=mj.MjData(model)
        geom=model.geom("surface").id
        eyes=[model.camera(side).id for side in ("left","right")]
        encoder=LandingSurfaceVision()
        def observe(flying):
            mj.mj_forward(model,data)
            return encoder.sample(model,data,[geom],eyes,model.body("fly").id,.01,flying)
        self.assertFalse(any(f["looming_active"] for f in observe(True)))
        model.geom_pos[geom,2]=-9
        self.assertTrue(any(f["looming_active"] for f in observe(True)))
        model.geom_pos[geom,2]=-8
        self.assertFalse(any(f["looming_active"] for f in observe(False)))
        self.assertFalse(any(f["looming_active"] for f in observe(True)))
        model.geom_pos[model.geom("blocker").id]=[0,0,-5]
        model.geom_pos[geom,2]=-7
        self.assertFalse(any(f["looming_active"] for f in observe(True)))
        encoder.reset()
        self.assertFalse(encoder.states)

    def test_sphere_angular_size(self):
        self.assertAlmostEqual(angular_diameter(2, 1), math.pi / 3)
        self.assertEqual(angular_diameter(1, 1), math.pi)

    def test_behind_camera_is_not_visible(self):
        self.assertFalse(field_visible([0, 0, 1], [0, 0, -1], 150, 0.1))
        self.assertTrue(field_visible([0, 0, -1], [0, 0, -1], 150, 0.1))

    def test_occlusion_or_visibility_gate_blocks_stimulus(self):
        looming = SphereLooming()
        looming.sample(10, 1, 0.1, True)
        self.assertFalse(looming.sample(8, 1, 0.1, True, visible=False)["looming_active"])
        self.assertFalse(looming.sample(6, 1, 0.1, True)["looming_active"])
        self.assertTrue(looming.sample(5, 1, 0.1, True)["looming_active"])

    def test_invalid_camera_geometry_rejected(self):
        for direction, forward, fovy, size in [
            ([0, 0], [0, 0, -1], 90, 0.1),
            ([0, 0, float("nan")], [0, 0, -1], 90, 0.1),
            ([0, 0, -1], [0, 0, -1], 90, -0.1),
            ([0, 0, -1], [0, 0, -1], 90, math.pi + 0.1),
        ]:
            with self.subTest(direction=direction, size=size):
                with self.assertRaises(ValueError):
                    field_visible(direction, forward, fovy, size)

    def test_compiled_camera_and_geometry_occlusion(self):
        try:
            import mujoco as mj
        except ModuleNotFoundError as error:
            if error.name != "mujoco":
                raise
            self.skipTest("MuJoCo required for compiled scene visibility")
        model = mj.MjModel.from_xml_string("""
            <mujoco>
              <worldbody>
                <body name="fly">
                  <camera name="eye" pos="0 0 0" fovy="90"/>
                </body>
                <geom name="finger" type="sphere" pos="0 0 -10" size="1"/>
                <geom name="blocker" type="box" pos="5 0 -5" size="1 1 0.5"/>
              </worldbody>
            </mujoco>
        """)
        data = mj.MjData(model)
        finger = model.geom("finger").id
        blocker = model.geom("blocker").id
        eye = model.camera("eye").id
        body = model.body("fly").id

        def observe():
            mj.mj_forward(model, data)
            view = finger_visibility(
                model, data, finger, data.geom_xpos[finger], 1, [eye], body,
            )[0]
            for field in ["in_field", "occluded", "visible"]:
                self.assertIs(type(view[field]), bool)
            self.assertEqual(json.loads(json.dumps(view, allow_nan=False)), view)
            return view

        self.assertTrue(observe()["visible"])
        model.geom_pos[blocker] = [0, 0, -5]
        blocked = observe()
        self.assertTrue(blocked["in_field"])
        self.assertTrue(blocked["occluded"])
        self.assertFalse(blocked["visible"])
        model.geom_pos[blocker] = [5, 0, -5]
        self.assertTrue(observe()["visible"])
        model.geom_pos[finger] = [0, 0, 10]
        self.assertFalse(observe()["visible"])

    def test_graded_spherical_scene_samples_real_geometry_and_occlusion(self):
        try:
            import mujoco as mj
        except ModuleNotFoundError as error:
            if error.name != "mujoco":
                raise
            self.skipTest("MuJoCo required for compiled graded scene sampling")
        model = mj.MjModel.from_xml_string("""
            <mujoco><worldbody>
              <body name="fly">
                <camera name="left" pos="0 .02 0" fovy="90"/>
                <camera name="right" pos="0 -.02 0" fovy="90"/>
              </body>
              <geom name="saved_sphere" type="sphere" pos="0 0 -10" size="1"/>
              <geom name="blocker" type="box" pos="5 0 -5" size="1 1 .5"/>
            </worldbody></mujoco>
        """)
        data = mj.MjData(model)
        sphere = model.geom("saved_sphere").id
        blocker = model.geom("blocker").id
        eyes = [model.camera(side).id for side in ("left", "right")]
        sources = [{"geom_id": sphere, "name": "saved_sphere", "enabled": True}]
        vision = SphereVision()
        def observe():
            mj.mj_forward(model, data)
            features = vision.sample(model, data, sources, eyes, model.body("fly").id, .01)
            self.assertEqual({feature["source_name"] for feature in features}, {"saved_sphere"})
            return features
        self.assertEqual(graded_visual_rates(observe()), {"LC4": 0., "LPLC2": 0.})
        model.geom_pos[sphere, 2] = -9
        features = observe()
        self.assertGreater(graded_visual_rates(features)["LC4"], 0)
        self.assertGreater(graded_visual_rates(features)["LPLC2"], 0)
        model.geom_pos[blocker] = [0, 0, -5]
        blocked = observe()
        self.assertTrue(all(feature["occluded"] for feature in blocked))
        self.assertEqual(graded_visual_rates(blocked), {"LC4": 0., "LPLC2": 0.})
        model.geom_pos[blocker] = [5, 0, -5]
        model.geom_pos[sphere, 2] = -8
        self.assertEqual(graded_visual_rates(observe()), {"LC4": 0., "LPLC2": 0.})
        model.geom_pos[sphere, 2] = -7
        self.assertGreater(graded_visual_rates(observe())["LC4"], 0)
        vision.forget(sphere)
        model.geom_size[sphere, 0] = 1.5
        self.assertEqual(graded_visual_rates(observe()), {"LC4": 0., "LPLC2": 0.})
        sources[0]["enabled"] = False
        self.assertEqual(graded_visual_rates(observe()), {"LC4": 0., "LPLC2": 0.})


class ElectricalCurrentTests(unittest.TestCase):
    def test_current_conserves_charge_and_units(self):
        currents = currents_nA([GapJunction("a", "b", 0.1)], {"a": -60, "b": -40})
        self.assertEqual(currents, {"a": 2.0, "b": -2.0})
        self.assertEqual(sum(currents.values()), 0)

    def test_equal_voltage_no_current(self):
        self.assertEqual(currents_nA([GapJunction("a", "b", 1)], {"a": -50, "b": -50}),
                         {"a": 0.0, "b": 0.0})

    def test_invalid_voltage_rejected(self):
        for voltage in [True, "invalid", float("inf"), float("nan")]:
            with self.subTest(voltage=voltage):
                with self.assertRaises(ValueError):
                    currents_nA([GapJunction("a", "b", 1)], {"a": voltage, "b": -50})

    def test_duplicates_and_missing_data_rejected(self):
        with self.assertRaises(ValueError):
            currents_nA([GapJunction("a", "b", 1), GapJunction("b", "a", 1)],
                        {"a": -50, "b": -40})
        with self.assertRaises(ValueError):
            currents_nA([GapJunction("a", "b", 1)], {"a": -50})
        with self.assertRaises(ValueError):
            GapJunction("a", "b", float("nan"))
