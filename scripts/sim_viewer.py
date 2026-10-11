"""Ensure native render threads finish before Python tears down OpenGL."""

import threading
import sys
from contextlib import contextmanager


class ViewerStateGuard:
    """Keep the application-owned integration state safe from native edits."""

    def __init__(self, model, data):
        import mujoco as mj
        import numpy as np

        self.mj, self.np = mj, np
        self.model, self.data = model, data
        self.flags = mj.mjtState.mjSTATE_INTEGRATION
        self.state = np.empty(mj.mj_stateSize(model, self.flags))
        self.candidate = np.empty_like(self.state)
        self.rejections = 0
        self.capture()

    def capture(self):
        self.mj.mj_getState(self.model, self.data, self.state, self.flags)

    def restore_if_changed(self):
        self.mj.mj_getState(self.model, self.data, self.candidate, self.flags)
        if self.np.array_equal(self.state, self.candidate):
            return False
        self.mj.mj_setState(self.model, self.data, self.state, self.flags)
        self.mj.mj_forward(self.model, self.data)
        self.mj.mj_setState(self.model, self.data, self.state, self.flags)
        self.rejections += 1
        if self.rejections == 1:
            print(
                "WARNING: ignored a native viewer physics edit to keep the controller "
                "synchronized. Use application controls; relaunch or the documented reset key to reset.",
                file=sys.stderr, flush=True,
            )
        return True


@contextmanager
def managed_viewer(model, data, **options):
    import mujoco.viewer

    before = set(threading.enumerate())
    handle = mujoco.viewer.launch_passive(model, data, **options)
    # launch_passive returns after creating its rendering thread, but close()
    # only requests shutdown; interpreter teardown must not race that thread.
    render_threads = [
        thread for thread in threading.enumerate()
        if thread not in before and thread.daemon
    ]
    try:
        yield handle
    finally:
        handle.close()
        for thread in render_threads:
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Native viewer render thread did not finish shutdown within 10 seconds")
