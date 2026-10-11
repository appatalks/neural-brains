"""Approved engineered navigation/landing baseline, not neural motor decoding."""

import math


class FlightNavigation:
    def __init__(self, half_size_cm):
        if not math.isfinite(half_size_cm) or half_size_cm < 3:
            raise ValueError("Navigation requires finite arena half-size >= 3 cm")
        self.half = half_size_cm
        self.origin = None
        self.start = None
        self.landing_start = None
        self.landing_origin = None

    def begin(self, position, timestamp):
        self.origin = list(position)
        self.start = timestamp
        self.landing_start = None
        self.landing_origin = None

    def reference(self, timestamp):
        if self.start is None:
            raise ValueError("Navigation requires an explicit takeoff")
        elapsed = max(0, timestamp-self.start)
        if self.landing_start is not None:
            fraction = min(1, max(0, (timestamp-self.landing_start)/1.2))
            smooth = fraction*fraction*(3-2*fraction)
            position = [self.landing_origin[0], self.landing_origin[1],
                        (1-smooth)*self.landing_origin[2]+smooth*.1278]
            return position, [0, 0, 0], 0
        # Smooth orbit remains bounded relative to the launch point, with
        # heading following its tangent rather than adding random jitter.
        radius = min(2.5, self.half*.25)
        omega = 20/radius
        angle = omega*max(0, elapsed-.3)
        if elapsed < .3:
            return [self.origin[0]+20*elapsed, self.origin[1], 1], [20, 0, 0], 0
        position = [self.origin[0]+6+radius*math.sin(angle),
                    self.origin[1]+radius*(1-math.cos(angle)), 1]
        velocity = [20*math.cos(angle), 20*math.sin(angle), 0]
        return position, velocity, angle

    def request_landing(self, position, timestamp):
        if self.landing_start is None:
            self.landing_start = timestamp
            self.landing_origin = list(position)


def landing_assistance(mass, position, velocity, rotation, target):
    import numpy as np
    force = mass*(1500*(np.asarray(target)-position)-100*velocity[3:]+[0, 0, 981])
    force = np.clip(force, -4*mass*981, 4*mass*981)
    desired = np.eye(3)
    error = sum(np.cross(rotation[:, i], desired[:, i]) for i in range(3))*.5
    torque = mass*.2*(800*error-50*velocity[:3])
    torque = np.clip(torque,-mass*.2*981,mass*.2*981)
    return np.concatenate([force, torque])
