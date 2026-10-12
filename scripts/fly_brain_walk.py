"""Opt-in genuine neural-output walking commands with explicit hybrid assumptions."""

import math


OUTPUT_IDS = {
    "BDN2": {"left": "720575940612364530", "right": "720575940647228468"},
    "oDN1": {"left": "720575940626730883", "right": "720575940620300308"},
    "DNa02": {"left": "720575940629327659", "right": "720575940604737708"},
    "DNa11": {"left": "720575940611735514", "right": "720575940623019544"},
}
DRIVE_KEYS = ("BPN", "P9_left", "P9_right", "FG")
BOUNDARY_LEAD_CM = 4.5
SCOPE = (
    "Genuine FlyWire BDN2/oDN1 rates request forward speed and DNa02 plus primary "
    "DNa11 (historical community DNa01) left/right "
    "rates request turning through the published learned walking policy. "
    "Rate filtering, thresholds and gains are reduced engineering assumptions; "
    "not reconstructed VNC/muscle gait or physiological calibration."
)
DRIVE_SCOPE = (
    "Explicit modeled BPN locomotor drive and privileged scene/ray cue-to-P9/FG "
    "activation. Inputs are assumptions, not spontaneous cognition or a "
    "reconstructed visual/tactile encoder. No direct input to decoded cells."
)


def validate_drive(value):
    if not isinstance(value, dict) or set(value) != set(DRIVE_KEYS):
        raise ValueError("Walking drive requires exact BPN/P9_left/P9_right/FG rates")
    if any(type(rate) not in (float, int) or not math.isfinite(rate) or not 0 <= rate <= 150
           for rate in value.values()):
        raise ValueError("Walking drive rates must be finite non-Boolean values in0..150Hz")
    return {key: float(value[key]) for key in DRIVE_KEYS}


def steering_candidates(primary_rows, annotation_by_id, model_ids):
    result = []
    for row in primary_rows:
        population = row.get("E")
        if population not in {"DNa02", "DNa11"}:
            continue
        for column, side in (("A", "left"), ("B", "right")):
            root = row.get(column, "").strip()
            annotation = annotation_by_id.get(root)
            valid_type = (population in {annotation["cell_type"], annotation["hemibrain_type"]}
                          if annotation is not None else False)
            if population == "DNa11" and annotation is not None:
                valid_type = annotation["cell_type"] == "DNae016" and row.get("C") == "DNa01"
            if (root != OUTPUT_IDS[population][side] or root not in model_ids or annotation is None
                    or annotation["side"] != side
                    or not valid_type):
                raise ValueError("Walking steering requires exact primary DNa02/model correspondence")
            result.append({"root_id": root, "side": side, "population": population, "in_model": True,
                           "cell_type": annotation["cell_type"], "hemibrain_type": annotation["hemibrain_type"],
                           "ambiguous_type_correspondence": False,
                           "historical_community_alias": row.get("C", ""),
                           "evidence_scope": "Exact primary identity; DNa11/DNa01 alias retained, functional-driver correspondence and motor gain not calibrated"})
    if len(result) != 4 or len({row["root_id"] for row in result}) != 4:
        raise ValueError("Expected primary DNa02 and DNa11 pairs")
    return result


def verified_outputs(metadata):
    if metadata.get("walking_control_enabled") is not True:
        raise ValueError("Neural walking requires explicitly enabled worker support")
    result = {}
    rows = metadata.get("sensorimotor_candidates", [])
    for population, expected in OUTPUT_IDS.items():
        selected = [row for row in rows if row.get("population") == population]
        if (len(selected) != 2 or {row.get("side"): row.get("root_id") for row in selected} != expected
                or any(not row.get("in_model") or row.get("ambiguous_type_correspondence") for row in selected)):
            raise ValueError(f"Neural walking requires exact verified {population} pair")
        result[population] = dict(expected)
    return result


class WalkingControl:
    def __init__(self, metadata):
        self.ids = verified_outputs(metadata)
        self.reset()

    def reset(self):
        self.sequence = 0
        self.end_ms = 0.
        self.episode = None
        self.rates = {value: 0. for group in self.ids.values() for value in group.values()}
        self.desired_speed = self.desired_turn = self.speed = self.turn = 0.
        self.turn_bias = 0.

    def accept(self, response):
        packet = response["neuron_activity"]
        count = response["sensorimotor_spikes"]
        drive = validate_drive(response["walking_drive_Hz"])
        start, end = packet["start_ms"], packet["end_ms"]
        if (type(packet["sequence"]) is not int or packet["sequence"] != self.sequence+1
                or type(packet["episode"]) is not int or packet["episode"] < 0
                or self.episode is not None and packet["episode"] != self.episode
                or type(start) not in (float, int) or type(end) not in (float, int)
                or not math.isfinite(start) or not math.isfinite(end)
                or abs(start-self.end_ms) > 1e-7 or not 0 < end-start <= 10.000001
                or response["brain_time_ms"] != end
                or any(type(count.get(value)) is not int or count[value] < 0 for value in self.rates)):
            raise ValueError("Walking commands require exact contiguous unreplayed<=10ms count packets")
        duration = (end-start)*.001
        decay = math.exp(-duration/.1)
        for value in self.rates:
            local_decay = math.exp(-duration/.25) if any(value in self.ids[name].values()
                                                        for name in ("DNa02", "DNa11")) else decay
            self.rates[value] = self.rates[value]*local_decay+(1-local_decay)*count[value]/duration
        bdn = sum(self.rates[value] for value in self.ids["BDN2"].values())
        odn = sum(self.rates[value] for value in self.ids["oDN1"].values())
        self.desired_speed = 2*max(0., min(1., (bdn-60)/80., (odn-15)/30.))
        difference = sum(self.rates[self.ids[name]["left"]]-self.rates[self.ids[name]["right"]]
                         for name in ("DNa02", "DNa11"))
        if drive["BPN"] and not any(drive[key] for key in ("P9_left", "P9_right", "FG")):
            bias_decay = math.exp(-duration/.2)
            self.turn_bias = self.turn_bias*bias_decay+(1-bias_decay)*difference
        difference -= self.turn_bias
        self.desired_turn = math.copysign(min(2., max(0., abs(difference)-8)*.08), difference)
        if self.desired_speed == 0:
            self.desired_turn = 0.
        self.sequence, self.end_ms, self.episode = packet["sequence"], end, packet["episode"]

    def advance(self, duration):
        if type(duration) not in (float, int) or not math.isfinite(duration) or not 0 < duration <= .01:
            raise ValueError("Walking command advancement requires finite0..10ms physical steps")
        self.speed += max(-10*duration, min(10*duration, self.desired_speed-self.speed))
        self.turn += max(-4*duration, min(4*duration, self.desired_turn-self.turn))
        return self.speed, self.turn

    def snapshot(self):
        return {"scope": SCOPE, "source_interval_end_ms": self.end_ms,
                "filtered_rates_Hz": dict(self.rates), "desired_speed_cm_s": self.desired_speed,
                "desired_turn_rad_s": self.desired_turn, "speed_cm_s": self.speed,
                "turn_rad_s": self.turn, "rate_filter_s": .1,
                "steering_filter_s": .25, "uncued_neural_turn_bias_Hz": self.turn_bias,
                "rate_mapping": "speed2*clip(min((BDN2sum-60)/80,(oDN1sum-15)/30)); steeringL-R minus uncued neural bias,deadband8,gain0.08,max2rad/s"}


def profile_metrics(samples, intervention=None):
    windows = {}
    for name, lo, hi in (("forward", .7, 1.2), ("left", 1.7, 2.2),
                         ("right", 2.7, 3.2), ("stop", 3.8, 4.2), ("rest", 4.5, 5.01)):
        selected = [row for row in samples if lo <= row["time_s"] < hi]
        if len(selected) < 30:
            return {"passed": False, "checks": {"complete_profile": False}, "missing_window": name,
                    "reason": "Walking profile requires complete physical windows through5s"}
        first, last = selected[0], selected[-1]
        windows[name] = {
            "mean_speed_cm_s": sum(row["speed_cm_s"] for row in selected)/len(selected),
            "mean_turn_rad_s": sum(row["turn_rad_s"] for row in selected)/len(selected),
            "displacement_mm": 10*math.hypot(*(last["position_cm"][i]-first["position_cm"][i] for i in (0, 1))),
            "yaw_change_rad": math.atan2(math.sin(last["yaw_rad"]-first["yaw_rad"]),
                                        math.cos(last["yaw_rad"]-first["yaw_rad"])),
        }
    minimum = min(row["upright_cosine"] for row in samples)
    if intervention in {"source-cut", "output-silence", "motor-disconnect"}:
        checks = {"motor_reference_absent": all(abs(row["motor_speed_cm_s"])+abs(row["motor_turn_rad_s"]) < 1e-12 for row in samples),
                  "no_forward_progress": windows["forward"]["displacement_mm"] < 1.}
    else:
        checks = {"forward_command": windows["forward"]["mean_speed_cm_s"] > .5,
                  "forward_motion": windows["forward"]["displacement_mm"] >= 5.,
                  "left_command": windows["left"]["mean_turn_rad_s"] > .2,
                  "left_motion": windows["left"]["yaw_change_rad"] > .1,
                  "right_command": windows["right"]["mean_turn_rad_s"] < -.2,
                  "right_motion": windows["right"]["yaw_change_rad"] < -.1,
                  "stop_command": windows["stop"]["mean_speed_cm_s"] < .1,
                  "stop_motion": windows["stop"]["displacement_mm"] < .5,
                  "rest_motion": windows["rest"]["displacement_mm"] < .5,
                  "rest_turn": abs(windows["rest"]["yaw_change_rad"]) < .1}
    checks["upright"] = minimum >= .8
    return {"windows": windows, "minimum_upright_cosine": minimum, "checks": checks,
            "passed": all(checks.values()), "scope": "Fixed bounded physical profile, not biological gait validation"}


class WalkingReference:
    def __init__(self):
        self.start = None

    def begin(self, position, timestamp, yaw=0., height=.1278):
        if (len(position) != 3 or any(not math.isfinite(value) for value in position)
                or not math.isfinite(timestamp) or not math.isfinite(yaw) or not math.isfinite(height) or height < .1278):
            raise ValueError("Walking reference requires finite measured position/time/yaw")
        self.start = self.time = timestamp
        self.height = height
        self.position = [position[0], position[1], height]
        self.yaw = yaw
        self.speed = self.turn = 0.

    def reference(self, timestamp):
        if self.start is None or not math.isfinite(timestamp) or timestamp < self.time-1e-9:
            raise ValueError("Neural walking reference needs initialized advancing time")
        dt = max(0., timestamp-self.time)
        yaw = self.yaw+self.turn*dt
        if abs(self.turn) < 1e-10:
            x = self.position[0]+self.speed*dt*math.cos(self.yaw)
            y = self.position[1]+self.speed*dt*math.sin(self.yaw)
        else:
            x = self.position[0]+self.speed/self.turn*(math.sin(yaw)-math.sin(self.yaw))
            y = self.position[1]+self.speed/self.turn*(math.cos(self.yaw)-math.cos(yaw))
        return [x, y, self.height], [self.speed*math.cos(yaw), self.speed*math.sin(yaw), 0.], yaw

    def update(self, position, timestamp, speed, turn, height=.1278):
        if (len(position) != 3 or any(not math.isfinite(value) for value in position)
                or not all(math.isfinite(value) for value in (timestamp, speed, turn,height))
                or height < .1278
                or not 0 <= speed <= 2 or abs(turn) > 2
                or self.start is None or not -1e-9 <= timestamp-self.time <= .011):
            raise ValueError("Neural reference requires bounded commands and contiguous measured state")
        dt = max(0., timestamp-self.time)
        predicted, _, yaw = self.reference(timestamp)
        self.height += min(1.,dt/.05)*(height-self.height)
        self.position = [predicted[axis]+min(1., dt/.2)*(position[axis]-predicted[axis])
                         for axis in (0, 1)]+[self.height]
        self.yaw, self.time, self.speed, self.turn = yaw, timestamp, speed, turn


def scene_drive(model, data, body, half_size_cm, walking):
    import mujoco as mj
    import numpy as np
    if type(walking) is not bool:
        raise ValueError("Walking drive needs explicit behavioral state")
    drive = dict.fromkeys(DRIVE_KEYS, 0.)
    if not walking:
        return drive, {"scope": DRIVE_SCOPE, "active": False}
    drive["BPN"] = 150.
    rotation = data.xmat[body].reshape(3, 3)
    yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    position = data.xpos[body]
    ranges = []
    hits = []
    for offset in (.7, 0., -.7):
        best, best_hit = 2.5, None
        for height in (0., .04):
            origin = position.copy()
            origin[2] += height
            direction = np.array([math.cos(yaw+offset), math.sin(yaw+offset), 0.])
            hit = np.zeros(1, dtype=np.int32)
            distance = mj.mj_ray(model, data, origin, direction,
                                 np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, body, hit)
            if 0 <= distance < best:
                name = model.geom(int(hit[0])).name
                if name not in {"groundplane", "pointer_target"} and not name.startswith("walker/"):
                    best, best_hit = float(distance), int(hit[0])
        ranges.append(best)
        hits.append(best_hit)
    lead = min(BOUNDARY_LEAD_CM,half_size_cm*.8)
    predicted = [position[0]+lead*math.cos(yaw), position[1]+lead*math.sin(yaw)]
    boundary = bool(max(abs(value) for value in predicted) >= half_size_cm-.6)
    if boundary:
        error = math.atan2(math.sin(math.atan2(-position[1], -position[0])-yaw),
                           math.cos(math.atan2(-position[1], -position[0])-yaw))
        drive["P9_left" if error >= 0 else "P9_right"] = 150.
    elif min(ranges) < 2.:
        drive["P9_left" if ranges[0] >= ranges[2] else "P9_right"] = 150.
    if ranges[1] < .4:
        drive["FG"] = 150.
    return drive, {"scope": DRIVE_SCOPE, "active": True, "ranges_cm": ranges,
                   "ray_geom_ids": hits, "boundary_cue": boundary,"boundary_lookahead_cm":lead}


def support_height(model,data,body):
    import mujoco as mj
    import numpy as np
    origin=data.xpos[body].copy()
    origin[2] += .1
    hit=np.zeros(1,dtype=np.int32)
    distance=mj.mj_ray(model,data,origin,np.array([0.,0.,-1.]),
                       np.array([1,0,0,0,0,0],dtype=np.uint8),True,body,hit)
    if distance < 0:
        raise RuntimeError("Terrain-following walking reference lost its physical support surface")
    return max(0.,float(origin[2]-distance))


def prescribed_drive(timestamp):
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Walking test drive requires advancing finite physical time")
    drive = dict.fromkeys(DRIVE_KEYS, 0.)
    if .2 <= timestamp < 4.2:
        drive["BPN"] = 150.
        if 1.2 <= timestamp < 2.2:
            drive["P9_left"] = 150.
        elif 2.2 <= timestamp < 3.2:
            drive["P9_right"] = 150.
        elif 3.2 <= timestamp < 4.2:
            drive["FG"] = 150.
    return drive
