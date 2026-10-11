import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fly_graphics import ObserverScene


@unittest.skipUnless(importlib.util.find_spec("mujoco"), "Requires MuJoCo")
class ObserverGraphicsTests(unittest.TestCase):
    def test_explicit_habitat_material_properties_are_preserved(self):
        import mujoco as mj
        import numpy as np

        model = mj.MjModel.from_xml_string(
            '<mujoco><asset><material name="leaf_material" specular=".2" shininess=".1"/>'
            '<material name="smooth_material" specular=".65" shininess=".7"/></asset>'
            '<worldbody><geom type="sphere" size="1" material="leaf_material"/></worldbody></mujoco>'
        )
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        observer = ObserverScene(model, data)
        np.testing.assert_array_equal(observer.model.mat_specular, model.mat_specular)
        np.testing.assert_array_equal(observer.model.mat_shininess, model.mat_shininess)

    def test_observer_changes_no_physics_or_sensor_model(self):
        import mujoco as mj
        import numpy as np

        model = mj.MjModel.from_xml_string(
            '<mujoco><asset><material name="grid" reflectance="0.2"/></asset>'
            '<worldbody><geom type="plane" size="10 10 1" material="grid"/>'
            '<body pos="0 0 1"><freejoint/><geom type="sphere" size=".1" mass="1"/>'
            '</body></worldbody></mujoco>'
        )
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        old_reflectance = model.mat_reflectance.copy()
        old_light = model.vis.headlight.ambient.copy()
        observer = ObserverScene(model, data)
        np.testing.assert_array_equal(model.mat_reflectance, old_reflectance)
        np.testing.assert_array_equal(model.vis.headlight.ambient, old_light)
        self.assertNotEqual(observer.model.mat_reflectance[0], model.mat_reflectance[0])
        for array in ["body_mass", "body_inertia", "geom_friction", "geom_size", "jnt_range"]:
            np.testing.assert_array_equal(getattr(model, array), getattr(observer.model, array))
        data.qpos[0] = 2
        model.geom_rgba[0] = [.1, .2, .3, 1]
        observer.sync()
        self.assertEqual(observer.data.qpos[0], 2)
        np.testing.assert_array_equal(observer.model.geom_rgba[0], model.geom_rgba[0])
        observer.data.qpos[0] = 100
        self.assertEqual(data.qpos[0], 2)
