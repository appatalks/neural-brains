"""Reduced, opt-in water forces in FlyBody cm/g/s; not a fluid solver."""

import math

SCOPE = (
    "Experimental hydrostatic buoyancy plus mass-proportional linear/angular drag. "
    "Circular flat-water volumes; primitive/mesh-bound displaced-volume approximation, "
    "geom-center buoyancy, implicit vertical force linearization and four-weight force caps. No CFD, waves, surface tension, "
    "wetting, drowning, swimming or neural water receptors."
)


class FluidPhysics:
    def __init__(self, model, environment, force_dt=None):
        import mujoco as mj
        import numpy as np

        if not environment.water_regions:
            raise ValueError("Fluid physics requires declared water regions")
        if model.opt.gravity[2] >= 0 or any(model.opt.gravity[:2]):
            raise ValueError("Reduced water requires downward vertical gravity")
        self.model = model
        self.regions = environment.water_regions
        self.gravity = -float(model.opt.gravity[2])
        self.dt = float(model.opt.timestep) if force_dt is None else force_dt
        if type(self.dt) not in (float,int) or not math.isfinite(self.dt) or not 0 < self.dt <= .01:
            raise ValueError("Water force interval must be finite in(0,10ms]")
        allowed = {obj.name+"_body" for obj in environment.movable_objects}
        self.geoms = {}
        for geom in range(model.ngeom):
            body = int(model.geom_bodyid[geom])
            name = mj.mj_id2name(model,mj.mjtObj.mjOBJ_BODY,body) or ""
            if (model.body_mass[body] <= 0 or not (name.startswith("walker/") or name in allowed)
                    or not (model.geom_contype[geom] or model.geom_conaffinity[geom])):
                continue
            kind, size = int(model.geom_type[geom]),model.geom_size[geom]
            if kind == mj.mjtGeom.mjGEOM_SPHERE:
                bounds = np.full(3,size[0])
                volume = 4*math.pi*size[0]**3/3
            elif kind == mj.mjtGeom.mjGEOM_BOX:
                bounds = size.copy()
                volume = 8*math.prod(size)
            elif kind == mj.mjtGeom.mjGEOM_ELLIPSOID:
                bounds = size.copy()
                volume = 4*math.pi*math.prod(size)/3
            elif kind == mj.mjtGeom.mjGEOM_CAPSULE:
                bounds = np.array([size[0],size[0],size[0]+size[1]])
                volume = 2*math.pi*size[0]**2*size[1]+4*math.pi*size[0]**3/3
            elif kind == mj.mjtGeom.mjGEOM_CYLINDER:
                bounds = np.array([size[0],size[0],size[1]])
                volume = 2*math.pi*size[0]**2*size[1]
            elif kind == mj.mjtGeom.mjGEOM_MESH:
                bounds = model.geom_aabb[geom,3:].copy()
                volume = 8*math.prod(bounds)
            else:
                raise ValueError(f"Reduced water does not support dynamic geometry type{kind}: {name}")
            if not math.isfinite(volume) or volume <= 0:
                raise ValueError("Water displaced-volume bounds must be finite and positive")
            self.geoms[geom] = body,bounds,float(volume),kind
        if not self.geoms:
            raise ValueError("Fluid physics requires supported physical dynamic bodies")
        self.volumes = {}
        self.radii = {}
        for body,bounds,volume,_ in self.geoms.values():
            self.volumes[body] = self.volumes.get(body,0.)+volume
            self.radii[body] = max(self.radii.get(body,0.),float(np.linalg.norm(bounds)))
        self.force = np.zeros((model.nbody,6))
        self.velocity = np.zeros(6)
        self.last = []

    def apply(self, data):
        import mujoco as mj
        import numpy as np

        self.force.fill(0)
        self.last = []
        for water in self.regions:
            surface = water.position_mm[2]*.1
            bottom = surface-water.depth_mm*.1
            submerged = {}
            stiffness = {}
            for geom,(body,bounds,volume,kind) in self.geoms.items():
                position = data.geom_xpos[geom]
                if math.hypot(position[0]*10-water.position_mm[0],
                              position[1]*10-water.position_mm[1]) >= water.radius_mm:
                    continue
                height = float(abs(data.geom_xmat[geom].reshape(3,3)[2])@bounds)
                low, high = float(position[2])-height,float(position[2])+height
                overlap = max(0.,min(high,surface)-max(low,bottom))
                if not overlap:
                    continue
                if kind == mj.mjtGeom.mjGEOM_SPHERE:
                    radius = bounds[0]
                    cap = lambda z: math.pi*z*z*(radius-z/3)
                    upper = min(2*radius,max(0.,surface-low))
                    lower = min(2*radius,max(0.,bottom-low))
                    volume_under = cap(upper)-cap(lower)
                    area = math.pi*max(0.,upper*(2*radius-upper)-lower*(2*radius-lower))
                else:
                    volume_under = volume*min(1.,overlap/(2*height))
                    area = volume/(2*height)*max(0,int(low>bottom)-int(high<surface))
                submerged[body] = submerged.get(body,0.)+volume_under
                stiffness[body] = stiffness.get(body,0.)+water.density_mg_mm3*self.gravity*area
                buoyancy = water.density_mg_mm3*volume_under*self.gravity
                self.force[body,2] += buoyancy
                self.force[body,3:] += np.cross(position-data.xipos[body],np.array([0.,0.,buoyancy]))
            for body,volume in submerged.items():
                fraction = min(1.,volume/self.volumes[body])
                mass = float(self.model.body_mass[body])
                mj.mj_objectVelocity(self.model,data,mj.mjtObj.mjOBJ_BODY,body,self.velocity,False)
                damping = mass*water.drag_rate_s*fraction
                self.force[body,:2] -= damping*(self.velocity[3:5]+self.dt*data.xfrc_applied[body,:2]/mass)/(1+self.dt*damping/mass)
                spring = stiffness[body]
                velocity_z = (self.velocity[5]+self.dt*(-self.gravity+
                    (self.force[body,2]+data.xfrc_applied[body,2])/mass))/(1+self.dt*damping/mass+self.dt**2*spring/mass)
                self.force[body,2] -= (damping+spring*self.dt)*velocity_z
                inertia = float(self.model.body_inertia[body].sum())/3
                self.force[body,3:] -= inertia*water.drag_rate_s*fraction*self.velocity[:3]
                self.last.append({"water":water.name,"body":self.model.body(body).name,
                                  "submerged_fraction":fraction,"displaced_volume_mm3":volume*1000})
        for body in self.volumes:
            cap = 4*float(self.model.body_mass[body])*self.gravity
            for part,limit in ((slice(0,3),cap),(slice(3,6),cap*self.radii[body])):
                norm = float(np.linalg.norm(self.force[body,part]))
                if norm > limit:
                    self.force[body,part] *= limit/norm
            if not np.isfinite(self.force[body]).all():
                raise RuntimeError("Reduced water produced nonfinite physical forces")
        data.xfrc_applied += self.force

    def snapshot(self):
        return {"scope":SCOPE,"surface_mode":"experimental-fluid","force_cap_body_weights":4,"force_interval_s":self.dt,
                "units":{"force":"g*cm/s^2","torque":"g*cm^2/s^2"},
                "immersed_bodies":[{**row,"force_torque":self.force[self.model.body(row["body"]).id].tolist()}
                                   for row in self.last]}
