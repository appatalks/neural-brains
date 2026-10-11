"""Observer-only visual quality; simulation and retinal model stay unchanged."""

import copy


class ObserverScene:
    def __init__(self, model, data):
        import mujoco as mj
        import numpy as np

        self.mj = mj
        self.np = np
        self.source_model, self.source_data = model, data
        self.model = copy.copy(model)
        self.data = mj.MjData(self.model)
        self.flags = mj.mjtState.mjSTATE_INTEGRATION
        self.state = np.empty(mj.mj_stateSize(model, self.flags))
        self.model.vis.quality.shadowsize = 8192
        self.model.vis.quality.offsamples = 4
        self.model.vis.headlight.ambient[:] = [0.25, 0.27, 0.30]
        self.model.vis.headlight.diffuse[:] = [0.75, 0.73, 0.68]
        self.model.vis.headlight.specular[:] = [0.3, 0.3, 0.3]
        for index in range(self.model.nmat):
            name = mj.mj_id2name(self.model, mj.mjtObj.mjOBJ_MATERIAL, index) or ""
            if name.endswith("_material"):
                continue
            if name == "grid":
                self.model.mat_reflectance[index] = 0.025
                self.model.mat_shininess[index] = 0.1
                self.model.mat_specular[index] = 0.1
            elif name.endswith("/eye"):
                self.model.mat_shininess[index] = 0.7
                self.model.mat_specular[index] = 0.55
            elif name.endswith("/wing"):
                self.model.mat_shininess[index] = 0.5
                self.model.mat_specular[index] = 0.3
            else:
                self.model.mat_shininess[index] = 0.25
                self.model.mat_specular[index] = 0.25
        self.sync()

    def sync(self):
        self.mj.mj_getState(self.source_model, self.source_data, self.state, self.flags)
        self.mj.mj_setState(self.model, self.data, self.state, self.flags)
        # Environment interactions change these model arrays rather than MjData.
        for name in ["geom_pos", "geom_quat", "geom_rgba"]:
            getattr(self.model, name)[:] = getattr(self.source_model, name)
        self.mj.mj_forward(self.model, self.data)
        self.mj.mj_setState(self.model, self.data, self.state, self.flags)
