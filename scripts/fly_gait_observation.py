"""Cached anatomical/contact lookup for the pinned FlyGym gait observation."""


class GaitObservationReader:
    def __init__(self, sim, fly_name):
        import numpy as np
        from flygym.anatomy import LEGS
        from flygym_demo.complex_terrain.hybrid_controller import HybridControllerObservation

        self.np = np
        self.observation = HybridControllerObservation
        self.sim = sim
        fly = sim.world.fly_lookup[fly_name]
        segment = type(fly).BODY_SEGMENT_CLASS
        order = fly.get_bodysegs_order()
        body_ids = sim._internal_bodyids_by_fly[fly_name]
        self.thorax = int(body_ids[order.index(segment("c_thorax"))])
        self.tarsi = np.array([body_ids[order.index(segment(f"{leg}_tarsus5"))] for leg in LEGS])
        geom_ids = sim._internal_geomid_by_bodyseg_by_fly[fly_name]
        segments = [segment(f"{leg}_{link}") for leg in LEGS for link in ("tibia", "tarsus1", "tarsus2")]
        self.output_by_geom = np.full(sim.mj_model.ngeom, -1, dtype=np.int32)
        for index, part in enumerate(segments):
            self.output_by_geom[geom_ids[part]] = index
        self.ground = np.zeros(sim.mj_model.ngeom, dtype=bool)
        self.ground[sim._internal_ground_geom_ids] = True

    def read(self):
        import mujoco as mj
        np = self.np
        model, data = self.sim.mj_model, self.sim.mj_data
        forces = np.zeros((18, 3))
        contacts = data.contact
        ncon = data.ncon
        g1, g2 = contacts.geom1[:ncon], contacts.geom2[:ncon]
        first, second = self.output_by_geom[g1], self.output_by_geom[g2]
        active = (
            (((first >= 0) & self.ground[g2]) | ((second >= 0) & self.ground[g1]))
            & ~contacts.exclude[:ncon].astype(bool)
        )
        wrench = np.zeros(6)
        for contact_id in np.where(active)[0]:
            mj.mj_contactForce(model, data, int(contact_id), wrench)
            world_force = contacts.frame[contact_id].reshape(3, 3).T @ wrench[:3]
            if first[contact_id] >= 0:
                forces[first[contact_id]] -= world_force
            if second[contact_id] >= 0:
                forces[second[contact_id]] += world_force
        return self.observation(
            thorax_z=float(data.xpos[self.thorax, 2]),
            tarsus5_z=data.xpos[self.tarsi, 2].copy(),
            stumbling_contact_forces=forces.reshape(6, 3, 3),
            fly_heading=data.xmat[self.thorax].reshape(3, 3)[:, 0].copy(),
        )
