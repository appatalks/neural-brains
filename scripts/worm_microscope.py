"""Local microscope-style preview for a bounded C. elegans environment."""

from __future__ import annotations

import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit

from worm_touch import simulate_anterior_touch, validate_touch_event
from worm_foraging import MAX_STEP_S, WormForagingModel
from worm_reference import OpenWormReference


DEFAULT_PORT = 8840
HTML_PATH = Path(__file__).with_name("worm_microscope.html")
MAX_MODEL_BYTES = 32_000_000
MAX_CELLS = 1_000
MAX_EDGES = 20_000
MAX_RECORDINGS = 10
MAX_SAMPLES = 5_000
MAX_STIMULUS_BYTES = 1_024


def server_address(port: int) -> tuple[str, int]:
    return "127.0.0.1", validate_port(port)


def validate_port(port: int) -> int:
    if type(port) is not int or port != DEFAULT_PORT:
        raise ValueError(
            f"The interactive worm microscope uses only port {DEFAULT_PORT}; "
            "alternate and ephemeral ports are disabled"
        )
    return port


def _finite_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_model(model: dict) -> dict:
    if not isinstance(model, dict) or type(model.get("schema_version")) is not int or model["schema_version"] != 1:
        raise ValueError("Worm model must use schema_version 1")
    connectome = model.get("connectome")
    activity = model.get("activity")
    if not isinstance(connectome, dict) or not isinstance(activity, dict):
        raise ValueError("Worm model requires connectome and activity objects")
    if not isinstance(connectome.get("sex"), str) or connectome["sex"] not in {"hermaphrodite", "male"}:
        raise ValueError("Worm connectome sex must be hermaphrodite or male")
    nodes = connectome.get("nodes")
    edges = connectome.get("edges")
    if (
        not isinstance(nodes, list)
        or not nodes
        or len(nodes) > MAX_CELLS
        or any(not isinstance(node, str) or not node for node in nodes)
        or len(set(nodes)) != len(nodes)
    ):
        raise ValueError("Connectome nodes must be a bounded list of unique cell labels")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        raise ValueError("Connectome edges must be a bounded list")
    edge_counts = connectome.get("edge_counts")
    if not isinstance(edge_counts, dict):
        raise ValueError("Connectome edge counts are required")
    node_set = set(nodes)
    seen_edges = set()
    chemical_count = 0
    electrical_count = 0
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Connectome edges must be objects")
        source = edge.get("source")
        target = edge.get("target")
        kind = edge.get("kind")
        weight = edge.get("weight_sections")
        if not isinstance(source, str) or not isinstance(target, str) or source not in node_set or target not in node_set:
            raise ValueError("Connectome edge endpoint is missing from the cell list")
        if not isinstance(kind, str) or kind not in {"chemical", "electrical_gap_junction"}:
            raise ValueError("Connectome edge type is not recognized")
        if not _finite_number(weight) or weight <= 0:
            raise ValueError("Connectome edge weight must be finite and positive")
        if kind == "electrical_gap_junction" and source >= target:
            raise ValueError("Electrical edges must be unique undirected cell pairs")
        key = kind, source, target
        if key in seen_edges:
            raise ValueError("Duplicate connectome edge")
        seen_edges.add(key)
        if kind == "chemical":
            chemical_count += 1
        else:
            electrical_count += 1
    if (
        type(edge_counts.get("chemical_directed")) is not int
        or edge_counts["chemical_directed"] != chemical_count
        or type(edge_counts.get("electrical_gap_undirected")) is not int
        or edge_counts["electrical_gap_undirected"] != electrical_count
        or type(edge_counts.get("chemical_self_entries_retained")) is not int
        or edge_counts["chemical_self_entries_retained"]
        != sum(edge["kind"] == "chemical" and edge["source"] == edge["target"] for edge in edges)
    ):
        raise ValueError("Connectome edge counts disagree with the edge list")
    diagonal_entries = connectome.get("electrical_diagonal_entries")
    if (
        not isinstance(diagonal_entries, list)
        or type(edge_counts.get("electrical_diagonal_entries_excluded")) is not int
        or edge_counts["electrical_diagonal_entries_excluded"] != len(diagonal_entries)
        or any(
            not isinstance(entry, dict)
            or not isinstance(entry.get("cell"), str)
            or entry["cell"] not in node_set
            or not _finite_number(entry.get("weight_sections"))
            or entry["weight_sections"] <= 0
            for entry in diagonal_entries
        )
    ):
        raise ValueError("Electrical diagonal audit entries disagree with their recorded count")

    recordings = activity.get("recordings")
    if (
        not isinstance(recordings, list)
        or not recordings
        or len(recordings) > MAX_RECORDINGS
    ):
        raise ValueError("Activity must contain a bounded list of recordings")
    seen_recordings = set()
    for recording in recordings:
        if not isinstance(recording, dict):
            raise ValueError("Activity recordings must be objects")
        recording_id = recording.get("recording_id")
        time_s = recording.get("time_s")
        traces = recording.get("traces")
        if not isinstance(recording_id, str) or not recording_id or recording_id in seen_recordings:
            raise ValueError("Recording IDs must be unique non-empty strings")
        seen_recordings.add(recording_id)
        if (
            not isinstance(time_s, list)
            or len(time_s) < 2
            or len(time_s) > MAX_SAMPLES
            or any(not _finite_number(value) for value in time_s)
            or any(right < left for left, right in zip(time_s, time_s[1:]))
        ):
            raise ValueError("Recording timestamps must be bounded, finite, and nondecreasing")
        if not isinstance(traces, list) or not traces or len(traces) > MAX_CELLS:
            raise ValueError("Recording must contain labeled cell traces")
        for count_field in ("sample_count", "matched_trace_count", "unlabeled_trace_rows", "unmatched_labeled_count"):
            if type(recording.get(count_field)) is not int or recording[count_field] < 0:
                raise ValueError(f"Recording {count_field} must be a nonnegative integer")
        if recording["sample_count"] != len(time_s) or recording["matched_trace_count"] != len(traces):
            raise ValueError("Recording counts disagree with its time axis or traces")
        unmatched_cells = recording.get("unmatched_labeled_cells")
        if (
            not isinstance(unmatched_cells, list)
            or any(not isinstance(cell, str) or not cell for cell in unmatched_cells)
            or recording["unmatched_labeled_count"] != len(unmatched_cells)
        ):
            raise ValueError("Unmatched activity-label count disagrees with its cell list")
        seen_cells = set()
        for trace in traces:
            if not isinstance(trace, dict):
                raise ValueError("Activity traces must be objects")
            cell = trace.get("cell")
            calcium = trace.get("calcium")
            if not isinstance(cell, str) or cell not in node_set or cell in seen_cells:
                raise ValueError("Activity cell must be a unique connectome node")
            seen_cells.add(cell)
            if (
                not isinstance(calcium, list)
                or len(calcium) != len(time_s)
                or any(not _finite_number(value) for value in calcium)
            ):
                raise ValueError(f"Calcium trace length or values are invalid for {cell}")
    return model


def create_server(
    port: int = DEFAULT_PORT,
    model: dict | None = None,
    reference_data_dir: Path | None = None,
) -> ThreadingHTTPServer:
    host, port = server_address(port)
    html = HTML_PATH.read_bytes()
    model_payload = None
    reference_manifest = None
    reference = None
    foraging_model = None
    foraging_lock = threading.Lock()
    health = {
        "status": "running",
        "model": "illustrative kinematic preview",
        "neural_model": False,
        "connectome_available": False,
        "recorded_activity_available": False,
        "touch_reversal_surrogate_available": False,
        "synthetic_foraging_available": False,
        "reference_images_available": False,
    }
    if model is not None:
        validate_model(model)
        model_payload = json.dumps(
            model, allow_nan=False, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
        if len(model_payload) > MAX_MODEL_BYTES:
            raise ValueError(f"Worm model exceeds {MAX_MODEL_BYTES} bytes")
        health = {
            **health,
            "model": "Cook 2019 connectome, calcium playback, and touch-relay surrogate",
            "connectome_available": True,
            "recorded_activity_available": True,
            "touch_reversal_surrogate_available": model["connectome"]["sex"] == "hermaphrodite",
            "connectome_cells": len(model["connectome"]["nodes"]),
            "chemical_edges": model["connectome"]["edge_counts"]["chemical_directed"],
            "electrical_edges": model["connectome"]["edge_counts"]["electrical_gap_undirected"],
            "recordings": len(model["activity"]["recordings"]),
        }
        if model["connectome"]["sex"] == "hermaphrodite":
            foraging_model = WormForagingModel(model["connectome"])
            health["synthetic_foraging_available"] = True
    if reference_data_dir is not None:
        reference = OpenWormReference(reference_data_dir)
        reference_manifest = reference.manifest
    health["reference_images_available"] = reference_manifest is not None
    expected_host = f"127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *_args):
            pass

        def respond(
            self,
            code: int,
            body: bytes,
            content_type: str,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", (
                "default-src 'none'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
                "base-uri 'none'; frame-ancestors 'none'"
            ))
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def check_local_request(self) -> bool:
            if self.headers.get("Host") != expected_host:
                self.respond(403, b'{"error":"non-local host"}', "application/json")
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{expected_host}":
                self.respond(403, b'{"error":"cross-origin request forbidden"}', "application/json")
                return False
            if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                self.respond(403, b'{"error":"cross-origin request forbidden"}', "application/json")
                return False
            if len(self.path) > 2048:
                self.respond(414, b'{"error":"request target too long"}', "application/json")
                return False
            return True

        def do_GET(self) -> None:
            if not self.check_local_request():
                return

            path = urlsplit(self.path).path
            if path == "/":
                self.respond(200, html, "text/html; charset=utf-8")
            elif path == "/health":
                self.respond(
                    200,
                    json.dumps(health, separators=(",", ":")).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
            elif path == "/api/model":
                if model_payload is None:
                    self.respond(503, b'{"error":"connectome/activity model not loaded"}', "application/json")
                else:
                    self.respond(200, model_payload, "application/json; charset=utf-8")
            elif path == "/api/reference/manifest":
                if reference_manifest is None:
                    payload = {
                        "available": False,
                        "message": "No verified real-image reference is configured; the kinematic field remains illustrative.",
                    }
                    self.respond(
                        200, json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )
                else:
                    self.respond(
                        200,
                        json.dumps(reference_manifest, separators=(",", ":")).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )
            elif path.startswith("/api/reference/frame/") and path.endswith(".png"):
                if reference is None:
                    self.respond(503, b'{"error":"reference recording not configured"}', "application/json")
                else:
                    frame_text = path.removeprefix("/api/reference/frame/").removesuffix(".png")
                    if not frame_text.isdecimal():
                        self.respond(400, b'{"error":"reference frame index must be a nonnegative integer"}', "application/json")
                        return
                    try:
                        image, metadata = reference.render_frame(int(frame_text))
                    except ValueError as error:
                        self.respond(
                            416,
                            json.dumps({"error": str(error)}, separators=(",", ":")).encode("utf-8"),
                            "application/json",
                        )
                        return
                    self.respond(
                        200,
                        image,
                        "image/png",
                        {
                            "X-Source-Frame": str(metadata["mask_frame"]),
                            "X-Source-Time": f'{metadata["source_time_s"]:.6f}',
                            "X-Raw-Snapshot": str(metadata["raw_snapshot"]),
                            "X-Raw-Snapshot-Time": f'{metadata["raw_snapshot_time_s"]:.6f}',
                        },
                    )
            else:
                self.respond(404, b'{"error":"not found"}', "application/json")

        def do_POST(self) -> None:
            if not self.check_local_request():
                return
            path = urlsplit(self.path).path
            if path == "/api/foraging/reset":
                if foraging_model is None:
                    self.respond(503, b'{"error":"synthetic foraging proxy unavailable for this model"}', "application/json")
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.respond(411, b'{"error":"valid Content-Length required"}', "application/json")
                    return
                if content_length != 0:
                    self.respond(400, b'{"error":"foraging reset takes no request body"}', "application/json")
                    return
                with foraging_lock:
                    result = foraging_model.reset()
                self.respond(
                    200,
                    json.dumps(result, allow_nan=False, separators=(",", ":")).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
            if path == "/api/foraging/step":
                if foraging_model is None:
                    self.respond(503, b'{"error":"synthetic foraging proxy unavailable for this model"}', "application/json")
                    return
                if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                    self.respond(415, b'{"error":"application/json required"}', "application/json")
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self.respond(411, b'{"error":"valid Content-Length required"}', "application/json")
                    return
                if content_length < 1 or content_length > MAX_STIMULUS_BYTES:
                    self.respond(413, b'{"error":"foraging request exceeds size limit"}', "application/json")
                    return
                try:
                    event = json.loads(self.rfile.read(content_length))
                    if not isinstance(event, dict) or set(event) != {"dt_s"}:
                        raise ValueError("Foraging step requires only dt_s")
                    if (
                        isinstance(event["dt_s"], bool)
                        or not isinstance(event["dt_s"], (int, float))
                        or not math.isfinite(event["dt_s"])
                        or event["dt_s"] <= 0
                        or event["dt_s"] > MAX_STEP_S
                    ):
                        raise ValueError(f"dt_s must be finite and between 0 and {MAX_STEP_S}")
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                    self.respond(400, json.dumps({"error": str(error)}).encode("utf-8"), "application/json")
                    return
                with foraging_lock:
                    result = foraging_model.step(event["dt_s"])
                self.respond(
                    200,
                    json.dumps(result, allow_nan=False, separators=(",", ":")).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
            if path != "/api/stimulus":
                self.respond(404, b'{"error":"not found"}', "application/json")
                return
            if model is None:
                self.respond(503, b'{"error":"connectome/activity model not loaded"}', "application/json")
                return
            if model["connectome"]["sex"] != "hermaphrodite":
                self.respond(422, b'{"error":"anterior touch relay is validated only for the hermaphrodite matrix"}', "application/json")
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                self.respond(415, b'{"error":"application/json required"}', "application/json")
                return
            try:
                content_length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.respond(411, b'{"error":"valid Content-Length required"}', "application/json")
                return
            if content_length < 0 or content_length > MAX_STIMULUS_BYTES:
                self.respond(413, b'{"error":"stimulus request exceeds size limit"}', "application/json")
                return
            try:
                event = validate_touch_event(json.loads(self.rfile.read(content_length)))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                self.respond(400, json.dumps({"error": str(error)}).encode("utf-8"), "application/json")
                return
            result = simulate_anterior_touch(model["connectome"])
            self.respond(
                200,
                json.dumps(result, allow_nan=False, separators=(",", ":")).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_HEAD(self) -> None:
            self.do_GET()

    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError:
        if reference is not None:
            reference.close()
        raise
    server.reference_source = reference
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model", type=Path, help="Prepared external JSON bundle from scripts/worm_data.py")
    parser.add_argument(
        "--reference-data-dir",
        type=Path,
        help="External data root containing the checksum-verified Open Worm recording",
    )
    args = parser.parse_args()
    model = None
    if args.model is not None:
        model = json.loads(args.model.expanduser().read_text(encoding="utf-8"))
    server = create_server(args.port, model, args.reference_data_dir)
    print(f"Worm microscope preview: http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if server.reference_source is not None:
            server.reference_source.close()


if __name__ == "__main__":
    main()
