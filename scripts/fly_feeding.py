"""Geometric taste exposure, persistent neural worker, and feeding readout."""

import hashlib
import json
import math
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from datasets import ROOT
from fly_environment import number, vector
from fly_activity import ActivityReader


@dataclass(frozen=True)
class FeedingConfig:
    position_mm: tuple
    radius_mm: float
    probe_mm: tuple
    seed: int

    @classmethod
    def load(cls, path):
        raw = json.loads(path.read_text())
        fields = {
            "schema_version", "source_position_mm", "source_radius_mm",
            "oral_probe_offset_mm", "contact_stimulation_Hz", "seed", "description", "readout",
        }
        if (
            not isinstance(raw, dict) or set(raw) != fields
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
        ):
            raise ValueError("Invalid live feeding configuration schema")
        if raw["contact_stimulation_Hz"] != 100:
            raise ValueError("First feeding bridge supports only the validated 100 Hz protocol")
        if type(raw["seed"]) is not int or raw["seed"] < 0:
            raise ValueError("Feeding seed must be a nonnegative integer")
        return cls(
            vector(raw["source_position_mm"], "sugar source position"),
            number(raw["source_radius_mm"], "sugar region radius", 0.01),
            vector(raw["oral_probe_offset_mm"], "oral probe offset"), raw["seed"],
        )

    def exposure(self, probe_position, enabled=True):
        if type(enabled) is not bool:
            raise ValueError("Sugar enabled state must be a boolean")
        position = vector(list(probe_position), "oral probe world position")
        distance = math.sqrt(sum((a-b)**2 for a,b in zip(position, self.position_mm)))
        return {"probe_position_mm": list(position), "distance_mm": distance,
                "sugar_enabled": enabled, "sugar_contact": bool(enabled and distance <= self.radius_mm)}


class BrainClient:
    def __init__(self, python: Path, data_dir: Path, output: Path, seed: int, takeoff: bool = False,
                 telemetry: bool = False, disconnect_visual_output: str | None = None,
                 dnp10_intervention: str | None = None, graded_vision: bool = False):
        if type(graded_vision) is not bool or graded_vision and not takeoff:
            raise ValueError("Graded vision requires verified takeoff populations")
        self.graded_vision = graded_vision
        if dnp10_intervention is not None and (
            not takeoff or not telemetry or dnp10_intervention not in {"sham", "silence"}
        ):
            raise ValueError("DNp10 research intervention requires takeoff, telemetry and sham or silence")
        if disconnect_visual_output is not None and (
            not takeoff or disconnect_visual_output not in {"LC4", "LPLC2", "both"}
        ):
            raise ValueError("Research disconnection requires verified takeoff population LC4, LPLC2 or both")
        self.responses = queue.Queue()
        self.thread = None
        self.pending = False
        self.expected_interval = None
        self.process = None
        self.stderr = (output / "brain-worker.log").open("x")
        try:
            self.process = subprocess.Popen(
                [str(python.expanduser().absolute()), str(ROOT / "scripts/fly_brain_worker.py"),
                 "--data-dir", str(data_dir), "--seed", str(seed)]
                + (["--takeoff-circuit"] if takeoff else [])
                + (["--neuron-telemetry"] if telemetry else [])
                + (["--disconnect-visual-output", disconnect_visual_output] if disconnect_visual_output else [])
                + (["--dnp10-intervention", dnp10_intervention] if dnp10_intervention else [])
                + (["--graded-vision"] if graded_vision else []),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                text=True, bufsize=1,
                env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
            )
            def read():
                for line in self.process.stdout:
                    self.responses.put(line)
                self.responses.put(None)
            self.thread = threading.Thread(target=read, daemon=True)
            self.thread.start()
            self.metadata = self.receive("ready", timeout=120)
            if self.metadata.get("neurons") != 127400 or self.metadata.get("aggregated_connections") != 14687178:
                raise RuntimeError("Brain worker did not load the validated whole-brain snapshot")
            if telemetry and self.metadata.get("neuron_activity_schema_version") != 1:
                raise RuntimeError("Brain worker does not support required neuron activity telemetry")
            if graded_vision and self.metadata.get("graded_vision_enabled") is not True:
                raise RuntimeError("Brain worker does not support required graded visual input")
            self.activity_reader = ActivityReader(self.metadata) if telemetry else None
        except Exception:
            self.abort()
            raise

    def receive(self, operation, timeout=30):
        try:
            line = self.responses.get(timeout=timeout)
        except queue.Empty as error:
            raise RuntimeError("Brain worker timed out; inspect brain-worker.log") from error
        if line is None:
            raise RuntimeError("Brain worker exited before responding; inspect brain-worker.log")
        reply = json.loads(line)
        if reply.get("op") == "error":
            raise RuntimeError(f"Brain worker: {reply.get('type')}: {reply.get('message')}")
        if reply.get("op") != operation:
            raise RuntimeError(f"Unexpected brain response, expected {operation}: {reply}")
        return reply

    def send(self, value):
        if self.process.poll() is not None:
            raise RuntimeError("Brain worker is no longer running")
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def begin_step(self, duration_ms, exposure, looming=False, visual_rates_Hz=None):
        if self.pending:
            raise RuntimeError("Previous brain interval has not completed")
        request = {"op": "step", "duration_ms": duration_ms, "sugar_contact": exposure, "looming_active": looming}
        if self.graded_vision:
            from fly_looming import validate_visual_rates
            visual_rates_Hz = validate_visual_rates(visual_rates_Hz)
            if type(looming) is not bool or looming != any(visual_rates_Hz.values()):
                raise ValueError("Looming active must match graded visual rates")
            request["visual_rates_Hz"] = visual_rates_Hz
        elif visual_rates_Hz is not None:
            raise ValueError("Rate input requires an explicitly enabled graded worker")
        self.send(request)
        self.pending = True
        self.expected_interval = (duration_ms, exposure, looming, visual_rates_Hz)

    def finish_step(self):
        if not self.pending:
            raise RuntimeError("No pending neural interval")
        reply = self.receive("step")
        duration, contact, looming, rates = self.expected_interval
        if reply.get("duration_ms") != duration or reply.get("sugar_contact") is not contact:
            raise RuntimeError("Neural response does not match the requested exposure interval")
        if reply.get("looming_active") is not looming:
            raise RuntimeError("Neural response disagrees with looming input")
        if self.graded_vision:
            from fly_looming import validate_visual_rates
            received_rates = validate_visual_rates(reply.get("visual_rates_Hz"))
            if received_rates != rates:
                raise RuntimeError("Neural response disagrees with graded input rates")
        for field in ["mn9_spikes", "network_spikes"]:
            if type(reply.get(field)) is not int or reply[field] < 0:
                raise RuntimeError("Neural response has invalid spike counts")
        if reply["mn9_spikes"] > reply["network_spikes"]:
            raise RuntimeError("Readout spike count exceeds total network spikes")
        gf = reply.get("giant_fiber_spikes")
        if not isinstance(gf, dict) or any(type(value) is not int or value < 0 for value in gf.values()):
            raise RuntimeError("Invalid giant-fiber spike readout")
        if sum(gf.values()) > reply["network_spikes"]:
            raise RuntimeError("Giant-fiber spike counts exceed network spikes")
        if not math.isfinite(reply.get("brain_time_ms", math.nan)):
            raise RuntimeError("Neural response has invalid simulation time")
        if self.activity_reader is not None:
            self.activity_reader.accept(reply)
        self.pending = False
        self.expected_interval = None
        return reply

    def reset(self):
        if self.pending:
            raise RuntimeError("Cannot reset a brain with an outstanding interval")
        self.send({"op": "reset"})
        reply = self.receive("reset")
        if self.activity_reader is not None:
            self.activity_reader.accept(reply, reset=True)
        return reply

    def abort(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if self.thread is not None:
                self.thread.join(timeout=5)
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stdin is not None:
                self.process.stdin.close()
        self.stderr.close()

    def close(self):
        try:
            if self.pending:
                self.finish_step()
            self.send({"op": "close"})
            self.receive("closed")
            code = self.process.wait(timeout=10)
            if code:
                raise RuntimeError(f"Brain worker exited with status {code}")
        finally:
            self.abort()


def feeding_hashes():
    return {
        "worker_sha256": hashlib.sha256((ROOT / "scripts/fly_brain_worker.py").read_bytes()).hexdigest(),
        "client_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "activity_module_sha256": hashlib.sha256((ROOT / "scripts/fly_activity.py").read_bytes()).hexdigest(),
    }
