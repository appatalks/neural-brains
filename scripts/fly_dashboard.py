"""Read-only companion dashboard; the native habitat remains independent.

Use ``with Dashboard(output, metadata) as dashboard`` and publish worker packets
without renumbering their episode/sequence. ``dashboard.url`` and dashboard.json
identify the browser URL. Only the latest packet/image is retained; this is not
a recorder. Pillow is imported only when RGB eye images are published.
``/api/status`` exposes eyes_available and eyes_revision, incremented only by
an image publication. Browsers can avoid requesting unavailable/unchanged PNGs
without requiring a publisher-supplied eye clock.
"""

from __future__ import annotations

import io
import errno
import json
import math
import queue
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


MAX_METADATA_BYTES = 32 * 1024 * 1024
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_EYES_BYTES = 8 * 1024 * 1024
MAX_EYES_PIXELS = 4_000_000
MAX_NEURONS = 200_000
DEFAULT_PORT = 8840


def validate_app_port(port):
    if type(port) is not int or port != DEFAULT_PORT:
        raise ValueError(f"The interactive fly app uses only port {DEFAULT_PORT}; alternate and ephemeral ports are disabled")
    return port


def _json_bytes(value, limit):
    payload = json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    if len(payload) > limit:
        raise ValueError("dashboard JSON payload exceeds size limit")
    return payload


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _nonnegative_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


class Dashboard:
    """Thread-safe latest-state HTTP publisher bound exclusively to 127.0.0.1."""

    def __init__(self, output: Path, metadata: dict, port: int = 0, connections=None, inputs=None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Dashboard port must be an integer in [0, 65535]")
        if inputs is not None:
            validate_app_port(port)
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        self._metadata = _json_bytes(metadata, MAX_METADATA_BYTES)
        frozen_metadata = json.loads(self._metadata)
        neuron_ids = frozen_metadata.get("neuron_ids")
        if (
            not isinstance(neuron_ids, list)
            or not neuron_ids
            or len(neuron_ids) > MAX_NEURONS
            or any(not isinstance(value, str) for value in neuron_ids)
            or len(set(neuron_ids)) != len(neuron_ids)
        ):
            raise ValueError("neuron_ids must be a bounded ordered list of unique strings")
        for key in ("input_ids", "gf_ids", "visual_input_ids"):
            values = frozen_metadata.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ValueError(f"{key} must contain string IDs")
        if frozen_metadata.get("mn9_id") is not None and not isinstance(
            frozen_metadata["mn9_id"], str
        ):
            raise ValueError("mn9_id must be a string")
        self._neuron_count = len(neuron_ids)
        self._session_id = uuid.uuid4().hex
        self._connections = connections
        self._inputs = inputs
        self._world = None
        self._world_revision = 0
        self._world_time_s = None
        if connections is not None:
            connections.validate_metadata(frozen_metadata)
        self._lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closed = False
        self._closed_status_written = False
        self._state = None
        self._eyes = None
        self._eyes_revision = 0
        self._habitat_status = None
        self._paused = None
        self._activity_summary = {
            "episode": None, "sequence": None, "episode_spikes": 0,
            "active_intervals": 0, "last_firing": None,
        }
        self._output = Path(output)
        self._html = Path(__file__).with_name("dashboard.html").read_bytes()
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def setup(self):
                self.request.settimeout(2)
                super().setup()

            def log_message(self, *args):
                pass

            def respond(self, code, body, content_type="application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Fly-Session", dashboard.session_id)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; img-src 'self' blob:; "
                    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError, TimeoutError):
                        pass

            def do_GET(self):
                # Reject DNS-rebinding hosts and browser requests from other origins.
                if self.headers.get("Host") != urlsplit(dashboard.url).netloc:
                    self.respond(403, b'{"error":"non-local host"}')
                    return
                origin = self.headers.get("Origin")
                if origin is not None and origin != dashboard.url.rstrip("/"):
                    self.respond(403, b'{"error":"cross-origin request forbidden"}')
                    return
                if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                    self.respond(403, b'{"error":"cross-origin request forbidden"}')
                    return
                if len(self.path) > 2048:
                    self.respond(414, b'{"error":"request target too long"}')
                    return
                path = urlsplit(self.path).path
                if path == "/":
                    self.respond(200, dashboard._html, "text/html; charset=utf-8")
                elif path == "/api/metadata":
                    self.respond(200, dashboard._metadata)
                elif path == "/api/status":
                    with dashboard._lock:
                        status = {
                            "status": "closed" if dashboard._closed else "running",
                            "state_available": dashboard._state is not None,
                            "eyes_available": dashboard._eyes is not None,
                            "eyes_revision": dashboard._eyes_revision,
                            "habitat_status": dashboard._habitat_status,
                            "paused": dashboard._paused,
                            "session_id": dashboard.session_id,
                            "connections_available": dashboard._connections is not None,
                            "world_available": dashboard._world is not None,
                            "world_revision": dashboard._world_revision,
                            "world_time_s": dashboard._world_time_s,
                            "interactive": dashboard._inputs is not None,
                        }
                    self.respond(200, _json_bytes(status, MAX_STATE_BYTES))
                elif path == "/api/connections":
                    if dashboard._connections is None:
                        self.respond(503, b'{"error":"verified connection index unavailable"}')
                        return
                    try:
                        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                        if set(query) - {"id", "direction", "offset", "limit"} or any(len(v) != 1 for v in query.values()):
                            raise ValueError("Invalid connection query fields")
                        result = dashboard._connections.lookup(
                            query.get("id", [""])[0], query.get("direction", [""])[0],
                            int(query.get("offset", ["0"])[0]), int(query.get("limit", ["25"])[0]),
                        )
                    except ValueError as error:
                        self.respond(400, _json_bytes({"error": str(error)}, 4096))
                        return
                    self.respond(200, _json_bytes(result, MAX_STATE_BYTES))
                elif path == "/api/activity-summary":
                    with dashboard._lock:
                        body = _json_bytes(dashboard._activity_summary, MAX_STATE_BYTES)
                    self.respond(200, body)
                elif path in ("/api/state", "/api/eyes", "/api/world"):
                    with dashboard._lock:
                        body = {"/api/state": dashboard._state, "/api/eyes": dashboard._eyes, "/api/world": dashboard._world}[path]
                    if body is None:
                        self.respond(503, b'{"available":false,"error":"not yet published"}')
                    else:
                        self.respond(
                            200, body,
                            "image/png" if path == "/api/eyes" else "image/jpeg" if path == "/api/world" else "application/json; charset=utf-8",
                        )
                else:
                    self.respond(404, b'{"error":"not found"}')

            def reject_method(self):
                self.respond(405, b'{"error":"read-only; use GET"}')

            def do_POST(self):
                from fly_browser import validate_input
                if dashboard._inputs is None:
                    self.reject_method()
                    return
                if (
                    self.headers.get("Host") != urlsplit(dashboard.url).netloc
                    or self.headers.get("Origin") != dashboard.url.rstrip("/")
                    or self.headers.get("X-Fly-Session") != dashboard.session_id
                    or self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site")
                ):
                    self.respond(403, b'{"error":"app session/origin mismatch"}')
                    return
                if self.path != "/api/input":
                    self.respond(404, b'{"error":"not found"}')
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 1024 or self.headers.get("Content-Type") != "application/json":
                        raise ValueError("Input must be a bounded JSON request")
                    event = validate_input(json.loads(self.rfile.read(length)))
                    dashboard._inputs.put_nowait(event)
                except (ValueError, UnicodeDecodeError) as error:
                    self.respond(400, _json_bytes({"error": str(error)}, 4096))
                    return
                except queue.Full:
                    self.respond(429, b'{"error":"input queue full; retry after simulation catches up"}')
                    return
                self.respond(202, b'{"status":"queued"}')

            do_PUT = do_PATCH = do_DELETE = reject_method
            do_HEAD = do_OPTIONS = do_TRACE = do_CONNECT = reject_method

        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                raise RuntimeError(
                    f"Dashboard port {port} is already in use. Reuse the running dashboard "
                    "or close it explicitly; no second port was selected."
                ) from error
            raise
        self._server.daemon_threads = True
        self._server.block_on_close = False
        self._url = f"http://127.0.0.1:{self._server.server_port}/"
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05},
            name="fly-dashboard", daemon=True,
        )
        try:
            self._output.mkdir(parents=True, exist_ok=True)
            self._write_status("running")
            self._thread.start()
        except BaseException:
            self._server.server_close()
            self._closed = True
            try:
                self._write_status("closed")
            except OSError:
                pass
            raise

    @property
    def session_id(self):
        return self._session_id

    @property
    def url(self):
        return self._url

    def _write_status(self, status):
        # A sibling staging file avoids readers observing a partially written URL.
        target = self._output / "dashboard.json"
        staging = self._output / f".dashboard-{self._server.server_port}.json"
        try:
            staging.write_bytes(_json_bytes({
                "url": self.url, "status": status, "session_id": self.session_id,
            }, 4096))
            staging.replace(target)
        finally:
            staging.unlink(missing_ok=True)

    def _validate_packet(self, packet):
        if not isinstance(packet, dict):
            raise ValueError("packet must be an object")
        activity = packet.get("neuron_activity")
        if (
            not isinstance(activity, dict)
            or not _integer(activity.get("schema_version"))
            or activity["schema_version"] != 1
        ):
            raise ValueError("neuron_activity schema_version 1 is required")
        for key in ("episode", "sequence", "network_spikes"):
            value = activity.get(key)
            if not _integer(value) or not 0 <= value <= 2**53 - 1:
                raise ValueError(f"neuron_activity.{key} must be a nonnegative integer")
        start, end = activity.get("start_ms"), activity.get("end_ms")
        if not _nonnegative_number(start) or not _nonnegative_number(end) or end < start:
            raise ValueError("activity interval must have finite ordered nonnegative bounds")
        indices, counts = activity.get("indices"), activity.get("counts")
        if not isinstance(indices, list) or not isinstance(counts, list):
            raise ValueError("activity indices/counts must be arrays")
        if len(indices) != len(counts) or len(indices) > self._neuron_count:
            raise ValueError("activity indices/counts length mismatch")
        previous = -1
        for index, count in zip(indices, counts):
            if not _integer(index) or not previous < index < self._neuron_count:
                raise ValueError("activity indices must be sorted unique valid neuron indices")
            if not _integer(count) or not 0 < count <= 2**53 - 1:
                raise ValueError("activity counts must be positive integers")
            previous = index
        if sum(counts) != activity["network_spikes"]:
            raise ValueError("network_spikes must equal the sum of interval counts")
        for key in ("brain_time_ms", "habitat_time_s", "eye_time_s"):
            if key in packet and not _nonnegative_number(packet[key]):
                raise ValueError(f"{key} must be finite and nonnegative")
        if "paused" in packet and not isinstance(packet["paused"], bool):
            raise ValueError("paused must be boolean")
        if "status" in packet and (
            not isinstance(packet["status"], str) or len(packet["status"]) > 128
        ):
            raise ValueError("status must be a string of at most 128 characters")

    def publish(self, packet: dict, eyes=None):
        """Atomically replace the latest immutable packet and optional RGB PNG.

        Invalid/oversized data raises ValueError without changing published state.
        Missing eyes retain the previous image, including on reset. Caller
        objects are never retained. Publishing after close raises RuntimeError.
        Republish the same activity episode/sequence with updated status, paused,
        or clocks for a heartbeat; the UI will not duplicate interval history.
        eye_time_s is the source render clock, never a dashboard-generated time.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("dashboard is closed")
        state = _json_bytes(packet, MAX_STATE_BYTES)
        frozen = json.loads(state)
        self._validate_packet(frozen)
        png = None
        if eyes is not None:
            shape = getattr(eyes, "shape", ())
            if (
                len(shape) != 3 or shape[2] != 3
                or shape[0] <= 0 or shape[1] <= 0
                or shape[0] * shape[1] > MAX_EYES_PIXELS
                or str(getattr(eyes, "dtype", "")) != "uint8"
            ):
                raise ValueError("eyes must be a bounded HxWx3 uint8 RGB array")
            from PIL import Image

            image = Image.fromarray(eyes.copy(), mode="RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", compress_level=1)
            png = buffer.getvalue()
            if len(png) > MAX_EYES_BYTES:
                raise ValueError("eye PNG exceeds size limit")
        with self._lock:
            if self._closed:
                raise RuntimeError("dashboard is closed")
            self._state = state
            activity = frozen["neuron_activity"]
            summary = self._activity_summary
            if summary["episode"] != activity["episode"]:
                summary = {
                    "episode": activity["episode"], "sequence": None,
                    "episode_spikes": 0, "active_intervals": 0, "last_firing": None,
                }
                self._activity_summary = summary
            if summary["sequence"] is None or activity["sequence"] > summary["sequence"]:
                summary["sequence"] = activity["sequence"]
                summary["episode_spikes"] += activity["network_spikes"]
                if activity["network_spikes"]:
                    summary["active_intervals"] += 1
                    summary["last_firing"] = activity
            self._habitat_status = frozen.get("status")
            self._paused = frozen.get("paused")
            if png is not None:
                self._eyes = png
                self._eyes_revision += 1

    def publish_world(self, pixels, time_s):
        if not _nonnegative_number(time_s):
            raise ValueError("World source clock must be finite and nonnegative")
        if len(pixels.shape) != 3 or pixels.shape[2] != 3 or pixels.shape[0]*pixels.shape[1] > MAX_EYES_PIXELS or str(pixels.dtype) != "uint8":
            raise ValueError("World image must be bounded uint8 RGB")
        from PIL import Image
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="JPEG", quality=95, subsampling=0)
        payload = buffer.getvalue()
        if len(payload) > MAX_EYES_BYTES:
            raise ValueError("World image exceeds size limit")
        with self._lock:
            if self._closed:
                raise RuntimeError("dashboard is closed")
            self._world, self._world_time_s = payload, time_s
            self._world_revision += 1

    def close(self):
        """Stop accepting connections, join the listener and persist closed URL."""
        with self._close_lock:
            with self._lock:
                if self._closed:
                    if not self._closed_status_written:
                        self._write_status("closed")
                        self._closed_status_written = True
                    return
                self._closed = True
            try:
                self._server.shutdown()
            finally:
                self._server.server_close()
                self._thread.join(timeout=3)
                self._write_status("closed")
                self._closed_status_written = True

    def __enter__(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("dashboard is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
