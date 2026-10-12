"""Engineered predictive arena/obstacle avoidance, not neural or retinal navigation."""

import math


SCOPE = (
    "Engineered predictive flight avoidance using privileged arena bounds, "
    "physical body pose, obstacle rays and bounded memory of detected geometry; learned wing policy. "
    "Not organic neural flight, biological vision or landing."
)
SPEED_CM_S = 20.
MAX_TURN_RAD_S = 3.
MAX_TURN_ACCEL_RAD_S2 = 12.
LOOKAHEAD_S = 1.2
OBSTACLE_BUFFER_CM = .8
MIN_HALF_SIZE_CM = 11.25/math.sqrt(2)


def obstacle_samples(model, data, body_id, known_ids=()):
    import mujoco as mj
    import numpy as np

    rotation = data.xmat[body_id].reshape(3, 3)
    yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    origin = data.xpos[body_id].copy()
    detected = set(known_ids)
    for height in (-.2,0.,.2):
        ray_origin=origin+np.array([0.,0.,height])
        for offset in (-.8, -.4, 0., .4, .8):
            direction = np.array([math.cos(yaw+offset), math.sin(yaw+offset), 0.])
            hit = np.zeros(1, dtype=np.int32)
            distance = mj.mj_ray(model, data, ray_origin, direction,
                                 np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, body_id, hit)
            if 0 <= distance <= SPEED_CM_S * LOOKAHEAD_S:
                geom = int(hit[0])
                name = mj.mj_id2name(model,mj.mjtObj.mjOBJ_GEOM,geom) or ""
                if int(model.geom_type[geom]) != 0 and not name.startswith("arena_wall_"):
                    detected.add(geom)
    # The planner's flight-height corridor excludes low ground cover;
    # recording every grass blade would exhaust memory without affecting it.
    detected = {geom for geom in detected
                if abs(float(data.geom_xpos[geom,2])-1.) <= float(model.geom_rbound[geom])+.2}
    if len(detected)>32:
        raise RuntimeError("Flight obstacle memory exceeded its explicit 32-geometry budget")
    return [{"position_cm":data.geom_xpos[geom].tolist(),"geom_id":geom,
             "radius_cm":float(model.geom_rbound[geom]),
             "distance_cm":float(np.linalg.norm(data.geom_xpos[geom]-origin))}
            for geom in sorted(detected)]


class FlightAvoidance:
    def __init__(self, half_size_cm):
        if not math.isfinite(half_size_cm) or half_size_cm < MIN_HALF_SIZE_CM-1e-9:
            raise ValueError("Predictive flight avoidance requires arena half-size >=79.55 mm")
        self.half = half_size_cm
        self.speed = SPEED_CM_S*min(1.,half_size_cm/15.)
        self.cruise_speed=self.speed
        self.maximum_turn = MAX_TURN_RAD_S
        self.maximum_turn_acceleration = MAX_TURN_ACCEL_RAD_S2
        self.reset()

    def reset(self):
        self.start = None
        self.time = None
        self.position = None
        self.yaw = 0.
        self.turn_rate = 0.
        self.selected_turn = 0.
        self.commands = 0
        self.obstacles = []
        self.known_obstacle_ids = ()
        self.launch_guard=False

    def begin(self, position, timestamp, yaw=0., launch=False):
        if (len(position) != 3 or any(not math.isfinite(v) for v in position)
            or not math.isfinite(timestamp) or not math.isfinite(yaw) or type(launch) is not bool):
            raise ValueError("Avoidance requires finite body position, heading and time")
        self.start = self.time = float(timestamp)
        self.position = list(position)
        self.position[2] = 1.
        self.yaw = yaw
        self.turn_rate = 0.
        self.selected_turn = 0.
        self.launch_guard=launch
        self.speed=0. if launch else self.cruise_speed

    def integrate(self, position, yaw, turn_rate, duration, speed=None):
        speed=self.speed if speed is None else speed
        if abs(turn_rate) < 1e-10:
            return [position[0]+speed*duration*math.cos(yaw),
                    position[1]+speed*duration*math.sin(yaw), 1.], yaw
        next_yaw = yaw+turn_rate*duration
        return [position[0]+speed/turn_rate*(math.sin(next_yaw)-math.sin(yaw)),
                position[1]+speed/turn_rate*(math.cos(yaw)-math.cos(next_yaw)), 1.], next_yaw

    def update(self, position, timestamp, obstacles):
        if self.start is None:
            raise ValueError("Avoidance requires explicit initialization")
        duration = timestamp-self.time
        if not math.isfinite(duration) or not -1e-9 <= duration <= .011:
            raise ValueError("Avoidance requires contiguous <=10 ms physical samples")
        if len(position) != 3 or any(not math.isfinite(v) for v in position):
            raise ValueError("Avoidance requires finite measured body position")
        if not isinstance(obstacles,list) or len(obstacles)>32 or any(
            not isinstance(obstacle,dict) or len(obstacle.get("position_cm",[]))!=3
            or any(not math.isfinite(v) for v in obstacle["position_cm"])
            or not math.isfinite(obstacle.get("radius_cm",0.)) or obstacle.get("radius_cm",0.)<0
            for obstacle in obstacles
        ):
            raise ValueError("Avoidance requires at most 32 finite physical obstacle samples")
        self.obstacles = [dict(obstacle,position_cm=list(obstacle["position_cm"])) for obstacle in obstacles]
        self.known_obstacle_ids = tuple(obstacle["geom_id"] for obstacle in obstacles if "geom_id" in obstacle)
        self.position, self.yaw = self.integrate(self.position, self.yaw, self.turn_rate, max(0., duration))
        error = [position[i]-self.position[i] for i in (0,1)]
        magnitude = math.hypot(*error)
        correction = min(1., max(0.,duration)/.2,
                         5.*max(0.,duration)/magnitude if magnitude else 1.)
        for axis in (0,1):
            self.position[axis] += correction*error[axis]
        self.time = timestamp
        maximum_turn = self.maximum_turn
        acceleration = self.maximum_turn_acceleration
        candidates = (0., -maximum_turn/2, maximum_turn/2, -maximum_turn, maximum_turn)
        def cost(candidate):
            predicted = list(position)
            predicted_reference = list(self.position)
            yaw, rate = self.yaw, self.turn_rate
            score = .02*candidate*candidate+.05*(candidate-self.selected_turn)**2
            # Prevent tiny shifts of the ray hit from repeatedly reversing
            # an unfinished avoidance maneuver.
            if candidate*self.selected_turn < 0:
                score += 5.
            for _ in range(24):
                change = acceleration*.05
                rate += max(-change, min(change, candidate-rate))
                predicted, yaw = self.integrate(predicted, yaw, rate, .05,self.cruise_speed)
                predicted_reference,_ = self.integrate(predicted_reference,yaw-rate*.05,rate,.05,self.cruise_speed)
                clearance = self.half-max(abs(v) for v in predicted[:2])-.5
                score += max(0., 3.-clearance)**2
                reference_clearance = self.half-max(abs(v) for v in predicted_reference[:2])-.5
                score += max(0.,3.-reference_clearance)**2
                for obstacle in self.obstacles:
                    if abs(predicted[2]-obstacle["position_cm"][2]) > obstacle.get("radius_cm",0.)+.2:
                        continue
                    separation = math.dist(predicted, obstacle["position_cm"])-obstacle.get("radius_cm",0.)-OBSTACLE_BUFFER_CM
                    score += 4*max(0., 2.-separation)**2
            return score
        selected = min(candidates, key=cost)
        self.selected_turn = selected
        delta = acceleration * max(0., duration)
        self.turn_rate += max(-delta, min(delta, selected-self.turn_rate))
        if self.launch_guard:
            direction=[math.cos(self.yaw),math.sin(self.yaw)]
            forward_clearance=min((self.half-.8-position[axis]*math.copysign(1.,component))/abs(component)
                                  for axis,component in enumerate(direction) if abs(component)>1e-6)
            safe_speed=max(0.,min(self.cruise_speed,(forward_clearance-2.)*2.))
            self.speed+=max(-40*duration,min(20*duration,safe_speed-self.speed))
            if timestamp-self.start>=.3 and self.speed>=self.cruise_speed-1e-6:
                self.launch_guard=False
        self.commands += int(abs(self.turn_rate) > .05)

    def reference(self, timestamp):
        if self.start is None:
            raise ValueError("Avoidance requires explicit initialization")
        dt = timestamp-self.time
        if not math.isfinite(dt) or not -1e-8 <= dt <= .011:
            raise ValueError("Avoidance reference must use the current physical horizon")
        position, yaw = self.integrate(self.position, self.yaw, self.turn_rate, max(0., dt))
        return position, [self.speed*math.cos(yaw), self.speed*math.sin(yaw), 0.], yaw

    def snapshot(self):
        return {"scope": SCOPE, "reference_position_cm": self.position, "reference_yaw_rad": self.yaw,
                "turn_rate_rad_s": self.turn_rate, "turn_command_samples": self.commands,
                "lookahead_s": LOOKAHEAD_S, "speed_cm_s": self.speed,
                "launch_clearance_guard":self.launch_guard,
                "cruise_speed_cm_s":self.cruise_speed,
                "maximum_turn_rad_s": self.maximum_turn,
                "maximum_turn_acceleration_rad_s2":self.maximum_turn_acceleration,
                "reference_feedback":"0.2 s soft tracking correction, bounded to 5 cm/s; changes only policy reference, never body pose",
                "obstacle_samples": self.obstacles}
