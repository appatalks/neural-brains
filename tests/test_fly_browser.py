import sys
import importlib.util
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_browser import validate_input, camera_input


class BrowserInputTests(unittest.TestCase):
    def test_camera_and_environment_inputs(self):
        for event in [
            {"kind": "pointer", "x": .2, "y": .8}, {"kind": "orbit", "dx": .3, "dy": -.1},
            {"kind": "pan", "dx": -.3, "dy": .1}, {"kind": "zoom", "delta": -.2},
            {"kind": "key", "key": "P"}, {"kind": "camera_reset"},
        ]:
            self.assertEqual(validate_input(event), event)
            self.assertIsNot(validate_input(event), event)

    def test_direct_steering_nonfinite_and_unknown_inputs_rejected(self):
        for event in [
            {"kind": "key", "key": "W"}, {"kind": "pointer", "x": True, "y": 0},
            {"kind": "pointer", "x": float("nan"), "y": 0},
            {"kind": "pointer", "x": -.1, "y": 0},
            {"kind": "zoom", "delta": 2}, {"kind": "camera_reset", "extra": 1},
            [], {"kind": []},
        ]:
            with self.subTest(event=event), self.assertRaises(ValueError):
                validate_input(event)

    @unittest.skipUnless(importlib.util.find_spec("mujoco"), "MuJoCo required for camera state test")
    def test_camera_controls_do_not_change_body_state(self):
        import mujoco as mj
        import numpy as np

        model = mj.MjModel.from_xml_string('<mujoco><worldbody><body pos="0 0 1"><freejoint/>'
                                         '<geom type="sphere" size=".1"/></body></worldbody></mujoco>')
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        qpos, qvel = data.qpos.copy(), data.qvel.copy()
        camera = mj.MjvCamera()
        camera_input(camera, {"kind": "camera_reset"}, 30, model, data)
        for event in [{"kind": "pan", "dx": .1, "dy": .2}, {"kind": "orbit", "dx": .1, "dy": .1},
                      {"kind": "zoom", "delta": -.2}]:
            camera_input(camera, event, 30, model, data)
        np.testing.assert_array_equal(data.qpos, qpos)
        np.testing.assert_array_equal(data.qvel, qvel)
        self.assertEqual(camera.type, mj.mjtCamera.mjCAMERA_FREE)

    @unittest.skipUnless(importlib.util.find_spec("mujoco"), "MuJoCo required for flight-unit camera test")
    def test_centimeter_camera_reset_and_zoom_preserve_physical_scale(self):
        import mujoco as mj
        import numpy as np

        model=mj.MjModel.from_xml_string('<mujoco><worldbody><geom type="sphere" size=".1"/></worldbody></mujoco>')
        data=mj.MjData(model)
        camera=mj.MjvCamera()
        camera_input(camera,{"kind":"camera_reset"},30,model,data,unit_scale=.1)
        np.testing.assert_array_equal(camera.lookat,[0,0,.2])
        camera.distance=.3
        camera_input(camera,{"kind":"zoom","delta":-1},30,model,data,unit_scale=.1)
        self.assertAlmostEqual(camera.distance,.2)
