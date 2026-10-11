import importlib.util
import os
import queue
import sys
import threading
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_world_renderer import BrowserInputs, WorldRenderer


class BrowserRoutingTests(unittest.TestCase):
    def test_camera_inputs_route_without_waiting_for_physics_consumer(self):
        inputs = BrowserInputs()
        event = {"kind": "orbit", "dx": .1, "dy": .1}
        inputs.put_nowait(event)
        _, routed = inputs.camera.get_nowait()
        self.assertEqual(routed, event)
        self.assertEqual(inputs.get_nowait(), event)
        inputs.put_nowait({"kind": "key", "key": "P"})
        self.assertTrue(inputs.camera.empty())

    def test_full_queue_does_not_partially_route_camera_input(self):
        inputs = BrowserInputs()
        for _ in range(128):
            inputs.put_nowait({"kind": "pointer", "x": 0, "y": 0})
        with self.assertRaises(queue.Full):
            inputs.put_nowait({"kind": "zoom", "delta": .1})
        self.assertTrue(inputs.camera.empty())


@unittest.skipUnless(importlib.util.find_spec("mujoco") and os.environ.get("MUJOCO_GL") == "egl",
                     "Explicit EGL context required for threaded graphics test")
class ThreadedRendererTests(unittest.TestCase):
    def scene(self):
        import mujoco as mj
        model = mj.MjModel.from_xml_string(
            '<mujoco><visual><global offwidth="1280" offheight="960"/></visual>'
            '<worldbody><geom type="plane" size="30 30 .1"/>'
            '<body name="fly" pos="0 0 1"><freejoint/><geom type="sphere" size=".1"/></body>'
            '</worldbody></mujoco>')
        data = mj.MjData(model)
        mj.mj_forward(model, data)
        return model, data

    def test_camera_updates_with_frozen_source_and_never_changes_physics(self):
        import numpy as np
        model, data = self.scene()
        initial = data.qpos.copy(), data.qvel.copy()
        inputs = BrowserInputs()
        published = threading.Event()
        frames = []

        def publish(image, clock):
            frames.append((image.copy(), clock))
            published.set()

        with WorldRenderer(model, data, 30, model.body("fly").id, inputs, publish) as renderer:
            self.assertTrue(published.wait(10))
            published.clear()
            inputs.put_nowait({"kind": "pan", "dx": .1, "dy": .1})
            self.assertTrue(published.wait(3))
            self.assertFalse(np.array_equal(frames[0][0], frames[-1][0]))
            self.assertEqual(frames[-1][1], 0)
            np.testing.assert_array_equal(data.qpos, initial[0])
            np.testing.assert_array_equal(data.qvel, initial[1])
            self.assertEqual(inputs.qsize(), 1)
            self.assertEqual(renderer.metrics()["camera_render_latency_samples"], 1)
            self.assertIsNotNone(renderer.target(640, 480))
            published.clear()
            data.qpos[0] = 1
            renderer.submit(model, data, .1, False)
            self.assertTrue(published.wait(3))
        self.assertFalse(renderer.thread.is_alive())

    def test_render_failure_is_explicit_and_thread_finishes(self):
        model, data = self.scene()
        def fail(*_):
            raise ValueError("frame publication failed")
        with self.assertRaisesRegex(RuntimeError, "frame publication failed"):
            with WorldRenderer(model, data, 30, model.body("fly").id, BrowserInputs(), fail) as renderer:
                deadline = time.monotonic()+5
                while renderer.thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(.01)
                renderer.check()
