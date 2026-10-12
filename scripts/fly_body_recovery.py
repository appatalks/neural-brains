"""Explicit bounded leg-servo righting attempts; no pose edits or root-body forces."""

import math

SCOPE="Experimental joint-actuator-only righting; not neural/VNC physiology. Failure disconnects only this fly's motor gains; its brain and passive physical body continue."


class BodyRecovery:
    def __init__(self,adapter,timeout=5.):
        if not math.isfinite(timeout) or timeout<=0:
            raise ValueError("Recovery requires a positive finite time limit")
        self.adapter=adapter
        self.timeout=timeout
        self.names=adapter.spec.name.split("\t")
        required=[f"{joint}_T{leg}_{side}" for leg in (1,2,3) for side in ("left","right")
                  for joint in ("coxa","coxa_abduct","femur","tibia","tarsus")]
        if any(name not in self.names for name in required):
            raise ValueError("Righting requires verified FlyBody leg-position actuator channels")
        self.phase="idle"
        self.started=None
        self.stable_since=None
        self.attempts=0
        self.successes=0
        self.failures=0
        self.events=[]

    def start(self,time_s):
        if self.phase!="idle":return
        self.phase="righting"
        self.started=time_s
        self.stable_since=None
        self.attempts+=1
        self.events.append({"time_s":time_s,"phase":"righting"})

    def observe(self,time_s,upright,contacts):
        if self.phase!="righting":return None
        if upright>.85 and contacts>0:
            self.stable_since=time_s if self.stable_since is None else self.stable_since
            if time_s-self.stable_since>=.3:
                self.phase="idle";self.successes+=1
                self.events.append({"time_s":time_s,"phase":"recovered"})
                return "recovered"
        else:self.stable_since=None
        if time_s-self.started>=self.timeout:
            self.phase="passive";self.failures+=1
            self.events.append({"time_s":time_s,"phase":"failed_passive"})
            return "failed"
        return None

    def action(self,time_s,walking_observation,walking_policy):
        import numpy as np
        if self.phase!="righting":
            raise ValueError("Recovery action requires an active physical righting attempt")
        if self.stable_since is not None:
            motor,_=walking_policy.action(walking_observation,self.adapter.projections["walking"]["spec"])
            return self.adapter.walking_action(motor)
        action=self.adapter.walking_action(np.zeros(self.adapter.projections["walking"]["spec"].shape))
        elapsed=time_s-self.started
        push_side="left" if int(elapsed/.8)%2==0 else "right"
        for leg in (1,2,3):
            for side in ("left","right"):
                push=side==push_side
                targets={"coxa":1.5 if push else -.15,"coxa_abduct":-.8 if push else .25,
                         "femur":.25 if push else 1.8,"tibia":1.15 if push else -1.1,
                         "tarsus":.7 if push else -.5}
                for joint,value in targets.items():
                    action[self.names.index(f"{joint}_T{leg}_{side}")]=value
        return np.clip(action,self.adapter.spec.minimum,self.adapter.spec.maximum)

    def snapshot(self):
        return {"scope":SCOPE,"phase":self.phase,"started_s":self.started,"timeout_s":self.timeout,
                "attempts":self.attempts,"successes":self.successes,"failures":self.failures,
                "events":list(self.events)}
