"""Experimental leg-actuator recovery; never resets or directly rotates the body."""

from dataclasses import dataclass, field


OFFSETS = (
    (-1.430459875597367, -1.6358007874775096, -1.4498331315111255,
     -0.9880979102698646, -0.7646699296884121, -1.5580111076330416, 1.493491066426714),
    (-1.658493176452215, 1.8824888961165076, 1.1607403179197915,
     -1.8999957129365637, 0.6456939227507328, -1.7993492973061294, 0.02328845268093227),
)
JOINT_ORDER = (
    ("coxa", "yaw"), ("coxa", "pitch"), ("coxa", "roll"),
    ("trochanterfemur", "pitch"), ("trochanterfemur", "roll"),
    ("tibia", "pitch"), ("tarsus1", "pitch"),
)


@dataclass
class Recovery:
    phase: str = "idle"
    phase_start: float = 0.0
    stable_since: float | None = None
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    events: list = field(default_factory=list)

    def transition(self, phase, time_s, uprightness):
        self.phase = phase
        self.phase_start = time_s
        self.events.append({"time_s": time_s, "phase": phase, "uprightness": uprightness})

    def update(self, time_s: float, uprightness: float):
        if self.phase == "idle" and uprightness < 0.25:
            self.attempts += 1
            self.stable_since = None
            self.transition("push", time_s, uprightness)
        elif self.phase == "push" and time_s - self.phase_start >= 0.3:
            self.transition("stabilize", time_s, uprightness)
        elif self.phase == "stabilize":
            if uprightness >= 0.8:
                if self.stable_since is None:
                    self.stable_since = time_s
                elif time_s - self.stable_since >= 0.5:
                    self.successes += 1
                    self.transition("idle", time_s, uprightness)
            else:
                self.stable_since = None
            if self.phase == "stabilize" and time_s - self.phase_start >= 2.0:
                self.failures += 1
                self.transition("failed", time_s, uprightness)
        return self.phase

    def reset(self, time_s):
        self.stable_since = None
        self.transition("idle", time_s, 1.0)


def recovery_offsets(dofs):
    import numpy as np

    values = []
    for dof in dofs:
        signature = (dof.child.link, dof.axis.value)
        if signature not in JOINT_ORDER or dof.child.pos not in {"lf", "lm", "lh", "rf", "rm", "rh"}:
            raise ValueError(f"Recovery does not support anatomical DoF {dof.name}")
        side = 0 if dof.child.pos.startswith("l") else 1
        values.append(OFFSETS[side][JOINT_ORDER.index(signature)])
    return np.array(values)
