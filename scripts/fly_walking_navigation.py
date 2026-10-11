"""Explicit engineered ground-reference avoidance; not connectome walking control."""

import math


class WalkingNavigation:
    def __init__(self, half_size_cm):
        if not math.isfinite(half_size_cm) or half_size_cm<3:
            raise ValueError("Walking navigation requires finite arena half-size >=3 cm")
        self.half=half_size_cm
        self.start=None

    def begin(self,position,timestamp,yaw=0.):
        self.position=list(position)
        self.position[2]=.1278
        self.time=timestamp
        self.start=timestamp
        self.yaw=yaw
        self.rate=0.
        self.correcting=False

    def update(self,position,timestamp):
        if self.start is None:
            raise ValueError("Walking reference requires initialization")
        dt=timestamp-self.time
        if not math.isfinite(dt) or not -1e-9<=dt<=.011:
            raise ValueError("Walking reference needs advancing <=10ms samples")
        dt=max(0.,dt)
        target,_,_=self.reference(timestamp)
        self.position=target
        if self.correcting:
            for axis in (0,1):
                self.position[axis]+=min(1.,dt/.2)*(position[axis]-self.position[axis])
        self.yaw+=self.rate*dt
        self.time=timestamp
        predicted=[position[0]+2.5*math.cos(self.yaw),position[1]+2.5*math.sin(self.yaw)]
        desired=0.
        if max(abs(v) for v in predicted)>=self.half-.6:
            inward=math.atan2(-position[1],-position[0])
            error=math.atan2(math.sin(inward-self.yaw),math.cos(inward-self.yaw))
            desired=max(-2.,min(2.,2*error))
        self.rate+=max(-4*dt,min(4*dt,desired-self.rate))
        self.correcting = self.correcting or abs(self.rate)>.05

    def reference(self,timestamp):
        if self.start is None:
            raise ValueError("Walking reference requires initialization")
        dt=max(0.,timestamp-self.time)
        yaw=self.yaw+self.rate*dt
        if abs(self.rate)<1e-8:
            position=[self.position[0]+2*dt*math.cos(self.yaw),self.position[1]+2*dt*math.sin(self.yaw),.1278]
        else:
            position=[self.position[0]+2/self.rate*(math.sin(yaw)-math.sin(self.yaw)),
                      self.position[1]+2/self.rate*(math.cos(self.yaw)-math.cos(yaw)),.1278]
        return position,[2*math.cos(yaw),2*math.sin(yaw),0.],yaw
