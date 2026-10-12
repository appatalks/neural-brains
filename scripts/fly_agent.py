"""Independent neural/controller state for one physical fly in a shared world."""

import math

from fly_brain_walk import WalkingControl,WalkingReference,scene_drive,support_height
from fly_feeding import BrainClient
from fly_flight_arena import FlyContactReader
from fly_flight_avoidance import FlightAvoidance,obstacle_samples
from fly_leg_extension import LegExtension
from fly_looming import SphereLooming,finger_visibility,LandingSurfaceVision
from fly_multibody import actor_environment,actor_observation,surrounding_drive
from fly_body_recovery import BodyRecovery
from fly_neural_landing import NeuralLanding
from fly_takeoff import assisted_force
from fly_unified import CONTROL_DT,MotorAdapter,WALK_EVERY
from fly_walking_navigation import WalkingNavigation


class FlyAgent:
    def __init__(self,env,index,data_dir,output,food,paths,walking,flying,
                 brain_guided_walking,flight_avoidance,neural_leg_extension,
                 brain_linked_landing,landing_surface_vision,actuator_recovery=False):
        import numpy as np
        from datasets import ROOT
        self.np=np
        self.env=env
        self.index=index
        self.id=index+1
        self.wing_pattern=paths["wing_pattern_fmech.npy"]
        self.proxy=actor_environment(env,index,paths["wing_pattern_fmech.npy"])
        self.walker=self.proxy.task.walker
        self.adapter=MotorAdapter(self.proxy)
        self.model,self.data=env.physics.model.ptr,env.physics.data.ptr
        self.body=self.model.body(self.walker.name+"/thorax").id
        self.eyes=[self.model.camera(self.walker.name+"/eye_"+side).id for side in ("left","right")]
        self.habitat=env.task.habitat
        self.peer_bodies=[self.model.body(w.name+"/thorax").id for w in env.task.walkers]
        self.recovery=BodyRecovery(self.adapter) if actuator_recovery else None
        self.actuator_ids=self.np.array([self.model.actuator(self.walker.name+"/"+name).id
                                        for name in self.adapter.spec.name.split("\t")])
        self.original_gain=self.model.actuator_gainprm[self.actuator_ids].copy()
        self.original_bias=self.model.actuator_biasprm[self.actuator_ids].copy()
        self.mass=float(env.physics.bind(self.walker.thorax).subtreemass)
        self.food=food
        self.walking,self.flying=walking,flying
        self.output=output
        output.mkdir()
        self.brain=BrainClient(ROOT/".venv/bin/python",data_dir,output,food.seed+index,
                               takeoff=True,telemetry=True,walking_control=brain_guided_walking)
        try:
            self.control=WalkingControl(self.brain.metadata) if brain_guided_walking else None
            self.reference=WalkingReference()
            self.navigation=WalkingNavigation(self.habitat.half_size_mm*.1)
            self.avoidance=FlightAvoidance(self.habitat.half_size_mm*.1) if flight_avoidance else None
            self.extension=LegExtension(self.brain.metadata) if neural_leg_extension else None
            self.landing=NeuralLanding(self.brain.metadata,self.habitat.half_size_mm*.1,
                                       contact_stabilization=brain_guided_walking) if brain_linked_landing else None
            self.surface=LandingSurfaceVision() if landing_surface_vision else None
            self.surface_ids=[self.model.geom(obj.name).id for obj in self.habitat.objects
                              if obj.name in {"fruit_food_surface","stone_landing_surface","bark_landing_patch",
                                              "wet_soil_patch","fallen_leaf_a","fallen_leaf_b","fallen_leaf_c"}]
            self.contacts=FlyContactReader(self.model,self.habitat,self.walker.name)
            self.looming={eye:SphereLooming() for eye in self.eyes}
            self.reset_state()
        except Exception:
            self.brain.close()
            raise

    def reset_state(self):
        self.trigger_time=None
        self.walk_motor=None
        self.landing_motor=None
        self.phase="walking"
        self.reply=None
        self.drive=None
        self.cues=None
        self.exposure=None
        self.fallen_since=None
        self.handoffs=[]
        self.landing_handoffs=[]
        self.flight_ticks=0
        self.flight_contacts=0
        self.minimum_upright=1.
        rotation=self.data.xmat[self.body].reshape(3,3)
        yaw=math.atan2(rotation[1,0],rotation[0,0])
        self.height=.1278+support_height(self.model,self.data,self.body)
        self.reference.begin(self.data.xpos[self.body],self.env.physics.time(),yaw,self.height)
        self.navigation.begin(self.data.xpos[self.body],self.env.physics.time(),yaw)

    def reset(self):
        self.brain.reset()
        self.proxy=actor_environment(self.env,self.index,self.wing_pattern)
        self.adapter=MotorAdapter(self.proxy)
        self.model,self.data=self.env.physics.model.ptr,self.env.physics.data.ptr
        self.contacts=FlyContactReader(self.model,self.habitat,self.walker.name)
        if self.control is not None:self.control.reset()
        if self.extension is not None:self.extension.reset()
        if self.landing is not None:self.landing.reset()
        if self.avoidance is not None:self.avoidance.reset()
        if self.surface is not None:self.surface.reset()
        if self.recovery is not None:self.recovery=BodyRecovery(self.adapter)
        self.looming={eye:SphereLooming() for eye in self.eyes}
        self.reset_state()

    def restore_motor_gains(self):
        self.model.actuator_gainprm[self.actuator_ids]=self.original_gain
        self.model.actuator_biasprm[self.actuator_ids]=self.original_bias

    def begin_brain(self,finger,finger_geom,sugar_enabled,finger_enabled,duration=.01):
        np=self.np
        views=finger_visibility(self.model,self.data,finger_geom,finger,.15,self.eyes,self.body) if finger_enabled else []
        by_eye={view["camera_id"]:view for view in views}
        features=[]
        for eye,state in self.looming.items():
            view=by_eye.get(eye)
            features.append(state.sample(view["distance_mm"]*10 if view else 1000.,1.5,duration,
                                         finger_enabled,view["visible"] if view else False))
        if self.surface is not None:
            features.extend(self.surface.sample(self.model,self.data,self.surface_ids,self.eyes,self.body,
                                                duration,self.phase=="flight"))
        probe=(self.data.xpos[self.body]+self.data.xmat[self.body].reshape(3,3)@np.array(self.food.probe_mm)*.1)*10
        self.exposure=self.food.exposure(probe.tolist(),sugar_enabled)
        self.drive=None
        if self.control is not None:
            self.drive,self.cues=scene_drive(self.model,self.data,self.body,self.habitat.half_size_mm*.1,
                                            self.phase in {"walking","post-landing-walk","landing-release"})
            self.drive,self.cues=surrounding_drive(self.drive,self.cues,self.model,self.data,self.body,self.peer_bodies)
            if self.recovery is not None and self.recovery.phase!="idle":
                self.drive={"BPN":0.,"P9_left":0.,"P9_right":0.,"FG":150.}
                self.cues={**self.cues,"recovery_input_scope":"Assumed FG stop input during actuator righting/passive isolation; not mapped tactile receptors"}
        self.brain.begin_step(duration*1000,self.exposure["sugar_contact"],
                              any(feature["looming_active"] for feature in features),walking_drive_Hz=self.drive)

    def prepare_interval(self):
        self.pending_reply=self.brain.finish_step()
        if self.avoidance is not None and self.trigger_time is not None and (
            self.landing is None or self.landing.request_time is None
        ):
            self.avoidance.update(self.data.xpos[self.body],self.env.physics.time(),
                obstacle_samples(self.model,self.data,self.body,self.avoidance.known_obstacle_ids))

    def velocity(self):
        import mujoco as mj
        result=self.np.zeros(6)
        mj.mj_objectVelocity(self.model,self.data,mj.mjtObj.mjOBJ_BODY,self.body,result,False)
        return result

    def action(self,observation,tick):
        import mujoco as mj
        np=self.np
        elapsed=self.env.physics.time()
        local=actor_observation(observation,self.walker)
        if self.recovery is not None and self.recovery.phase!="idle":
            self.phase="actuator-righting" if self.recovery.phase=="righting" else "passive-failed-recovery"
            self.landing_force=np.zeros(6)
            if self.control is not None:self.control.advance(CONTROL_DT)
            if self.recovery.phase=="passive":return np.zeros(self.adapter.spec.shape)
            self.height=.1278
            self.reference.update(self.data.xpos[self.body],elapsed,0.,0.,self.height)
            policy_obs=self.adapter.walking_observation(local,0.,self.reference)
            return self.recovery.action(elapsed,policy_obs,self.walking)
        self.phase="walking" if self.trigger_time is None else "assisted-launch" if elapsed-self.trigger_time<.3 else "flight"
        if self.landing is not None and self.landing.request_time is not None and self.trigger_time is not None:
            self.phase=self.landing.phase(elapsed)
        speed,turn=self.control.advance(CONTROL_DT) if self.control is not None else (2.,0.)
        self.landing_force=np.zeros(6)
        if self.landing is not None and self.landing.request_time is not None and self.trigger_time is not None:
            action,self.landing_motor=self.landing.motor_action(self.adapter,self.walking,self.flying,local,elapsed,
                                      None if tick%WALK_EVERY==0 else self.landing_motor)
            self.landing_force=self.landing.assistance(self.mass,elapsed,self.data.xpos[self.body],
                                                       self.velocity(),self.data.xmat[self.body].reshape(3,3))
            self.data.xfrc_applied[self.body]+=self.landing_force
        elif self.trigger_time is None:
            reference=self.navigation
            if self.control is not None:
                if tick%WALK_EVERY==0:self.height=.1278+support_height(self.model,self.data,self.body)
                self.reference.update(self.data.xpos[self.body],elapsed,speed,turn,self.height)
                reference=self.reference
            else:
                self.navigation.update(self.data.xpos[self.body],elapsed)
            if tick%WALK_EVERY==0 or self.walk_motor is None:
                self.walk_motor,_=self.walking.action(self.adapter.walking_observation(local,2.,reference),
                                                      self.adapter.projections["walking"]["spec"])
            action=self.adapter.walking_action(self.walk_motor)
        else:
            motor,_=self.flying.action(self.adapter.flight_observation(local,navigation=self.avoidance),
                                       self.adapter.projections["flight"]["spec"])
            action=self.adapter.flight_action(motor)
            if self.phase=="assisted-launch":
                from flybody.quaternions import mult_quat
                desired=self.proxy.task.launch_origin.copy()
                desired[0]+=20*(elapsed-self.trigger_time);desired[2]=1.
                target_velocity=None
                quat=np.array([math.cos(math.radians(47.5)/2),0,-math.sin(math.radians(47.5)/2),0])
                if self.avoidance is not None:
                    desired,target_velocity,yaw=self.avoidance.reference(elapsed)
                    quat=mult_quat(np.array([math.cos(yaw/2),0,0,math.sin(yaw/2)]),quat)
                rotation=np.zeros(9);mj.mju_quat2Mat(rotation,quat)
                self.data.xfrc_applied[self.body]+=assisted_force(
                    self.mass,self.data.xpos[self.body],self.velocity(),self.data.xmat[self.body].reshape(3,3),
                    rotation.reshape(3,3),desired,target_velocity)
        if self.extension is not None:
            activation=self.extension.advance(CONTROL_DT,self.phase=="flight")
            if self.phase=="flight":action=self.adapter.leg_extension_action(action,activation)
        if self.landing is not None:self.landing.decoder.advance(CONTROL_DT,self.phase=="flight")
        self.data.xfrc_applied[self.body,:3]+=np.array(self.habitat.wind_force((self.velocity()[3:]*10).tolist()))*.1
        return action

    def observe(self):
        time=self.env.physics.time()
        contacts=self.contacts.sample(self.data)
        upright=float(self.data.xmat[self.body].reshape(3,3)[2,2])
        self.minimum_upright=min(self.minimum_upright,upright)
        if self.phase=="flight":
            self.flight_ticks+=1;self.flight_contacts+=int(contacts>0)
        if self.landing is not None and self.landing.request_time is not None:
            self.landing.observe(time,contacts,upright,float(self.np.linalg.norm(self.velocity()[3:])),
                                 self.data.xpos[self.body])
            if self.landing.release_time is not None and time>=self.landing.release_time and self.trigger_time is not None:
                self.trigger_time=None;self.walk_motor=None
                rotation=self.data.xmat[self.body].reshape(3,3)
                self.height=.1278+support_height(self.model,self.data,self.body)
                self.reference.begin(self.data.xpos[self.body],time,math.atan2(rotation[1,0],rotation[0,0]),self.height)
        if self.phase=="walking" and upright<.5 and contacts:
            self.fallen_since=time if self.fallen_since is None else self.fallen_since
            if time-self.fallen_since>=.15:
                if self.recovery is None:return f"Fly {self.id} fallen-state safety pause; Reset required."
                self.recovery.start(time)
                self.trigger_time=None
                if self.landing is not None:self.landing.reset(clear_neural=False)
                rotation=self.data.xmat[self.body].reshape(3,3)
                self.reference.begin(self.data.xpos[self.body],time,math.atan2(rotation[1,0],rotation[0,0]))
        else:self.fallen_since=None
        if self.recovery is not None:
            transition=self.recovery.observe(time,upright,contacts)
            if transition=="failed":
                self.model.actuator_gainprm[self.actuator_ids]=0.
                self.model.actuator_biasprm[self.actuator_ids]=0.
            elif transition=="recovered":
                self.walk_motor=None
                rotation=self.data.xmat[self.body].reshape(3,3)
                self.reference.begin(self.data.xpos[self.body],time,math.atan2(rotation[1,0],rotation[0,0]),
                                     .1278+support_height(self.model,self.data,self.body))
                if self.control is not None:self.control.speed=self.control.turn=0.
        if max(abs(value)*10 for value in self.data.xpos[self.body,:2])>=self.habitat.half_size_mm-5:
            return f"Fly {self.id} boundary safety pause; Reset required."
        return None

    def accept_brain(self,safety_stopped):
        reply=self.pending_reply
        if abs(reply["brain_time_ms"]-self.env.physics.time()*1000)>1e-5:
            raise RuntimeError(f"Fly {self.id} brain/body clocks diverged")
        self.reply=reply
        if self.control is not None:self.control.accept(reply)
        if self.extension is not None:self.extension.accept(reply)
        rotation=self.data.xmat[self.body].reshape(3,3)
        yaw=math.atan2(rotation[1,0],rotation[0,0])
        before_position,before_velocity=self.data.qpos.copy(),self.data.qvel.copy()
        if self.landing is not None and self.landing.accept(reply,self.phase=="flight",
            self.data.xpos[self.body],self.velocity()[3:],yaw):
            self.landing_handoffs.append(dict(self.landing.request));self.landing_motor=None
        if (self.trigger_time is None and not safety_stopped
                and (self.recovery is None or self.recovery.phase=="idle")
                and sum(reply["giant_fiber_spikes"].values())):
            if self.landing is not None and self.landing.request_time is not None:
                self.landing.reset(clear_neural=False);self.landing_motor=None
            self.trigger_time=self.env.physics.time()
            self.proxy.task.launch_time=self.trigger_time
            self.proxy.task.launch_origin=self.data.xpos[self.body].copy()
            self.proxy.task.wbpg.reset(initial_phase=.5)
            if self.avoidance is not None:
                self.avoidance.begin(self.data.xpos[self.body],self.trigger_time,yaw,launch=True)
            self.handoffs.append({"time_s":self.trigger_time,"qpos_preserved":True,"qvel_preserved":True})
        if not self.np.array_equal(before_position,self.data.qpos) or not self.np.array_equal(before_velocity,self.data.qvel):
            raise RuntimeError("Per-fly controller handoff modified shared physical state")

    def snapshot(self):
        return {"id":self.id,"body_prefix":self.walker.name,"brain_seed":self.food.seed+self.index,
                "world_color":("blue","green","amber")[self.index],
                "phase":self.phase,"position_mm":(self.data.xpos[self.body]*10).tolist(),
                "upright_cosine":float(self.data.xmat[self.body].reshape(3,3)[2,2]),
                "network_spikes":self.reply["network_spikes"] if self.reply is not None else None,
                "recovery":self.recovery.snapshot() if self.recovery is not None else None,
                "awareness_cues":self.cues,
                "walking_control":self.control.snapshot() if self.control is not None else None,
                "brain_linked_landing":self.landing.snapshot() if self.landing is not None else None}
