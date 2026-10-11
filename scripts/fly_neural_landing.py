"""Actual DNp10 initiation with explicitly assumed, assisted landing motor dynamics."""

import math

from fly_leg_extension import LegExtension

BRAKE_S=.35
DESCENT_S=.75

SCOPE = (
    "Actual verified DNp10 spikes initiate an assumed latched landing request. "
    "Brake, descent, wing-to-leg transition and external force/torque assistance "
    "are reduced engineering assumptions, not reconstructed VNC/muscle physiology. "
    "DNp10 causal biological evidence supports leg extension, not this whole touchdown controller."
)


class NeuralLanding:
    def __init__(self, metadata, half_size_cm=11.25):
        from fly_walking_navigation import WalkingNavigation
        self.walk_navigation=WalkingNavigation(half_size_cm)
        self.decoder = LegExtension(metadata)
        self.reset()

    def reset(self, clear_neural=True):
        if clear_neural:
            self.decoder.reset()
        self.request_time = None
        self.request = None
        self.origin = None
        self.yaw = 0.
        self.speed = 0.
        self.contact_since = None
        self.descent_start=None
        self.descent_ready_since=None
        self.touchdown_time = None
        self.release_time = None
        self.walk_origin = None
        self.stable_walk_steps = 0
        self.walk_navigation.start=None

    def accept(self, response, flying, position, velocity, yaw):
        self.decoder.accept(response)
        if type(flying) is not bool:
            raise ValueError("Landing requires explicit flight state")
        counts = response["sensorimotor_spikes"]
        count = sum(counts[value] for value in self.decoder.ids)
        if not flying or not count or self.request_time is not None:
            return False
        if (len(position)!=3 or len(velocity)!=3 or not math.isfinite(yaw)
            or any(not math.isfinite(v) for v in [*position,*velocity])):
            raise ValueError("Landing request requires finite measured body state")
        self.request_time = response["brain_time_ms"]/1000
        self.request = {"episode":response["neuron_activity"]["episode"],
                        "sequence":response["neuron_activity"]["sequence"],
                        "time_s":self.request_time,"neuron_ids":self.decoder.ids,
                        "interval_spikes":count}
        self.origin = list(position)
        self.yaw = yaw
        self.speed = min(20.,math.hypot(*velocity[:2]))
        return True

    def phase(self, timestamp):
        if self.request_time is None:
            return "flight"
        if self.release_time is not None and timestamp>=self.release_time:
            return "post-landing-walk"
        if self.touchdown_time is not None:
            return "landing-release"
        return "neural-request-assisted-landing"

    def reference(self, timestamp):
        if self.request_time is None or timestamp<self.request_time-1e-9:
            raise ValueError("Landing reference requires a real prior DNp10 request")
        elapsed = max(0.,timestamp-self.request_time)
        braking = min(elapsed,BRAKE_S)
        # A short smooth brake in the existing travel direction precedes
        # descent; these are assumed motor dynamics, not DN physiology.
        distance = self.speed*(braking-braking**2/BRAKE_S+braking**3/(3*BRAKE_S**2))
        position = [self.origin[0]+distance*math.cos(self.yaw),
                    self.origin[1]+distance*math.sin(self.yaw),self.origin[2]]
        velocity = [self.speed*(1-braking/BRAKE_S)**2*math.cos(self.yaw),
                    self.speed*(1-braking/BRAKE_S)**2*math.sin(self.yaw),0.]
        fraction = 0. if self.descent_start is None else min(1.,max(0.,(timestamp-self.descent_start)/DESCENT_S))
        smooth = fraction*fraction*(3-2*fraction)
        position[2] = (1-smooth)*self.origin[2]+smooth*.1278
        velocity[2] = -(self.origin[2]-.1278)*6*fraction*(1-fraction)/DESCENT_S
        if self.touchdown_time is not None:
            return self.walk_navigation.reference(timestamp)
        return position,velocity,self.yaw

    def assistance(self, mass, timestamp, position, velocity, rotation):
        import numpy as np

        if self.request_time is None:
            return np.zeros(6)
        target,target_velocity,yaw = self.reference(timestamp)
        elapsed=max(0.,timestamp-self.request_time)
        pitch_fraction=min(1.,elapsed/.8)
        pitch=-math.radians(47.5)*(1-pitch_fraction*pitch_fraction*(3-2*pitch_fraction))
        cy,sy=math.cos(yaw),math.sin(yaw)
        cp,sp=math.cos(pitch),math.sin(pitch)
        desired=np.array([[cy*cp,-sy,cy*sp],[sy*cp,cy,sy*sp],[-sp,0,cp]])
        support=max(0.,min(1.,(float(position[2])-.15)/.15))
        force=mass*(1500*(np.array(target)-position)-80*(velocity[3:]-target_velocity)+[0,0,981*support])
        error=sum(np.cross(rotation[:,i],desired[:,i]) for i in range(3))*.5
        torque=mass*.1*(800*error-50*velocity[:3])
        force=np.clip(force,-4*mass*981,4*mass*981)
        torque=np.clip(torque,-mass*.1*981,mass*.1*981)
        scale=1.
        if self.touchdown_time is not None:
            fraction=min(1.,max(0.,(timestamp-self.touchdown_time)/1.))
            scale=1-fraction*fraction*(3-2*fraction)
        return scale*np.concatenate([force,torque])

    def observe(self, timestamp, floor_contacts, upright, speed, position):
        if self.request_time is None:
            return
        stable=floor_contacts>0 and upright>.9 and speed<3.
        if self.descent_start is None:
            ready=timestamp-self.request_time>=.8 and upright>.94 and speed<3.
            if ready:
                self.descent_ready_since=timestamp if self.descent_ready_since is None else self.descent_ready_since
                if timestamp-self.descent_ready_since>=.1-1e-9:
                    self.descent_start=timestamp
            else:
                self.descent_ready_since=None
        if self.touchdown_time is None:
            if stable and self.descent_start is not None and timestamp-self.descent_start>=DESCENT_S:
                self.contact_since = timestamp if self.contact_since is None else self.contact_since
                if timestamp-self.contact_since>=.2:
                    self.touchdown_time=timestamp
                    self.release_time=timestamp+1.
                    self.walk_origin=list(position)
                    self.walk_navigation.begin(position,timestamp,self.yaw)
            else:
                self.contact_since=None
        else:
            self.walk_navigation.update(position,timestamp)
            if timestamp>=self.release_time:
                self.stable_walk_steps=self.stable_walk_steps+1 if upright>.8 and floor_contacts>0 else 0

    def motor_action(self, adapter, walking, flying, observation, timestamp, walking_motor):
        """Keep the published channels intact through the assumed transition."""
        flight_action=None
        if timestamp-self.request_time<.7:
            motor,_=flying.action(adapter.flight_observation(observation,navigation=self),
                                  adapter.projections["flight"]["spec"])
            flight_action=adapter.flight_action(motor)
        if walking_motor is None:
            walking_motor,_=walking.action(adapter.walking_observation(observation,0,navigation=self),
                                           adapter.projections["walking"]["spec"])
        leg_action=adapter.walking_action(walking_motor)
        blend=min(1.,max(0.,(timestamp-self.request_time)/.7))
        action=leg_action if flight_action is None else (1-blend)*flight_action+blend*leg_action
        return action,walking_motor

    def snapshot(self):
        return {"scope":SCOPE,"neural_request":self.request,"touchdown_time_s":self.touchdown_time,
                "assistance_release_time_s":self.release_time,"stable_unassisted_walking_steps":self.stable_walk_steps,
                "activation":self.decoder.activation,"braking_duration_s":BRAKE_S,"descent_duration_s":DESCENT_S,
                "descent_start_s":self.descent_start,
                "validation":"Not validated by presence of this controller"}
