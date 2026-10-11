import importlib.util
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sim_viewer import managed_viewer


@unittest.skipUnless(importlib.util.find_spec("mujoco"), "Requires a MuJoCo environment")
class ViewerShutdownTests(unittest.TestCase):
    def test_close_waits_for_native_render_thread(self):
        stopped = threading.Event()
        finished = threading.Event()
        workers = []

        class Handle:
            def close(self):
                stopped.set()

        def launch(*args, **kwargs):
            def render():
                stopped.wait()
                finished.set()
            worker = threading.Thread(target=render, daemon=True)
            worker.start()
            workers.append(worker)
            return Handle()

        with patch("mujoco.viewer.launch_passive", side_effect=launch):
            with managed_viewer(None, None) as handle:
                self.assertFalse(finished.is_set())
                self.assertIsInstance(handle, Handle)
        self.assertTrue(finished.is_set())
        self.assertFalse(workers[0].is_alive())


if __name__ == "__main__":
    unittest.main()
