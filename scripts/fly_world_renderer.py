"""Thread-owned observer rendering from immutable, latest-only body snapshots."""

import copy
import queue
import threading
import time
from collections import deque
from types import SimpleNamespace

from fly_browser import camera_input
from fly_finger import pointer_target
from fly_graphics import ObserverScene
from fly_performance import PhaseTimings


class BrowserInputs(queue.Queue):
    def __init__(self):
        super().__init__(maxsize=128)
        self.camera = queue.Queue(maxsize=128)
        self.route_lock = threading.Lock()

    def put_nowait(self, event):
        camera = event["kind"] in {"orbit", "pan", "zoom", "camera_reset"}
        with self.route_lock:
            if self.full() or (camera and self.camera.full()):
                raise queue.Full
            super().put_nowait(event)
            if camera:
                self.camera.put_nowait((time.perf_counter(), event.copy()))


class WorldRenderer:
    def __init__(self, model, data, half_size_mm, body_id, inputs, publish, graphics=True, unit_scale=1,
                 initial_distance=None):
        import mujoco as mj
        import numpy as np

        self.mj, self.np = mj, np
        self.model = copy.copy(model)
        self.flags = mj.mjtState.mjSTATE_INTEGRATION
        self.state_size = mj.mj_stateSize(model, self.flags)
        self.half = half_size_mm
        self.body = body_id
        self.inputs = inputs
        self.publish = publish
        self.graphics = graphics
        self.unit_scale = unit_scale
        self.initial_distance = initial_distance
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.snapshot = None
        self.revision = 0
        self.optical = None
        self.timings = {}
        self.latencies = deque(maxlen=120)
        self.thread = threading.Thread(target=self._run, name="fly-world-renderer", daemon=True)
        self.submit(model, data, 0, False)
        self.thread.start()
        if not self.ready.wait(15):
            self.close()
            raise RuntimeError("World renderer startup timed out")
        self.check()

    def check(self):
        with self.lock:
            error = self.error
        if error is not None:
            raise RuntimeError(f"World renderer failed: {error}") from error

    def submit(self, model, data, time_s, follow):
        self.check()
        state = self.np.empty(self.state_size)
        self.mj.mj_getState(model, data, state, self.flags)
        arrays = {name: getattr(model, name).copy() for name in ["geom_pos", "geom_quat", "geom_rgba"]}
        with self.lock:
            self.snapshot = (state, arrays, float(time_s), bool(follow))
            self.revision += 1
        self.wake.set()

    def target(self, x, y, plane_z=1.5):
        with self.lock:
            optical = self.optical
        if optical is None:
            return None
        return pointer_target(optical, self.mj.MjrRect(0, 0, 1280, 960), x, y, plane_z)

    def metrics(self):
        with self.lock:
            values = list(self.latencies)
            return {
                "phases": copy.deepcopy(self.timings),
                "camera_render_latency_samples": len(values),
                "camera_render_latency_p95_ms": float(self.np.percentile(values, 95)) if values else None,
                "scope": "Accepted camera input to encoded frame publication, latest 120 samples; excludes browser decode/display.",
            }

    def select_body(self,body_id):
        if type(body_id) is not int or not 0 <= body_id < self.model.nbody:
            raise ValueError("World observer requires a valid physical body index")
        with self.lock:
            self.body=body_id
        self.wake.set()

    def _run(self):
        mj, np = self.mj, self.np
        try:
            source_data = mj.MjData(self.model)
            observer = ObserverScene(self.model, source_data) if self.graphics else None
            model = observer.model if observer else self.model
            data = observer.data if observer else source_data
            camera = mj.MjvCamera()
            camera_input(camera, {"kind": "camera_reset"}, self.half, self.model, source_data, self.unit_scale)
            if self.initial_distance is not None:
                camera.distance = self.initial_distance
            timing = PhaseTimings()
            revision = -1
            follow = False
            requested_follow = False
            last_render = 0.0
            with mj.Renderer(model, height=960, width=1280) as renderer:
                self.ready.set()
                while not self.stop.is_set():
                    self.wake.wait(timeout=1/30)
                    self.wake.clear()
                    remaining = 1/30-(time.perf_counter()-last_render)
                    if remaining > 0 and self.stop.wait(remaining):
                        break
                    with self.lock:
                        snapshot, candidate_revision = self.snapshot, self.revision
                    changed = candidate_revision != revision
                    if changed:
                        state, arrays, source_time, candidate_follow = snapshot
                        mj.mj_setState(self.model, source_data, state, self.flags)
                        for name, values in arrays.items():
                            getattr(self.model, name)[:] = values
                        mj.mj_forward(self.model, source_data)
                        mj.mj_setState(self.model, source_data, state, self.flags)
                        if candidate_follow != requested_follow:
                            follow = candidate_follow
                            requested_follow = candidate_follow
                        revision = candidate_revision
                    accepted = []
                    while True:
                        try:
                            received, event = self.inputs.camera.get_nowait()
                        except queue.Empty:
                            break
                        camera_input(camera, event, self.half, self.model, source_data, self.unit_scale)
                        follow = False
                        accepted.append(received)
                    if not changed and not accepted:
                        continue
                    camera.type = mj.mjtCamera.mjCAMERA_TRACKING if follow else mj.mjtCamera.mjCAMERA_FREE
                    camera.trackbodyid = self.body
                    with timing.measure("observer_snapshot_sync"):
                        if observer:
                            observer.sync()
                    with timing.measure("world_gpu_render_readback"):
                        renderer.update_scene(data, camera)
                        image = renderer.render()
                    optical = mj.mjv_averageCamera(renderer.scene.camera[0], renderer.scene.camera[1])
                    projection = SimpleNamespace(**{
                        name: np.asarray(getattr(optical, name)).copy() if name in {"pos", "forward", "up"}
                        else float(getattr(optical, name))
                        for name in ["pos", "forward", "up", "frustum_near", "frustum_bottom", "frustum_top", "frustum_center"]
                    })
                    with timing.measure("world_image_encode_publish"):
                        self.publish(image, source_time)
                    last_render = time.perf_counter()
                    with self.lock:
                        self.optical = projection
                        self.timings = timing.snapshot()
                        self.latencies.extend((last_render-stamp)*1000 for stamp in accepted)
        except Exception as error:
            with self.lock:
                self.error = error
            self.ready.set()

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            raise RuntimeError("World renderer failed to shut down")
        self.check()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
