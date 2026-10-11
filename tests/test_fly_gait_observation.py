import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@unittest.skipUnless(importlib.util.find_spec("flygym"), "Pinned biomechanics environment required")
class GaitObservationTests(unittest.TestCase):
    def test_exact_observation_actions_and_reset_parity(self):
        import numpy as np
        from fly_environment import Environment
        from fly_gait_observation import GaitObservationReader
        from fly_walking import build_scene
        from flygym_demo.complex_terrain import (
            HybridControllerObservation, HybridTurningController, PreprogrammedSteps,
            apply_locomotion_action,
        )
        sim, fly, reference, reset, *_ = build_scene(
            Environment.load(ROOT / "experiments/fly-walking/planted-habitat.json"),
        )
        reader = GaitObservationReader(sim, fly.name)
        cached = HybridTurningController(
            timestep=sim.timestep, preprogrammed_steps=PreprogrammedSteps(),
            output_dof_order=fly.get_actuated_jointdofs_order("position"),
        )
        cached.reset(seed=0)
        for step in range(1000):
            if step == 500:
                reset()
                cached.reset(seed=0)
            before = HybridControllerObservation.from_sim(sim, fly.name)
            after = reader.read()
            self.assertEqual(before.thorax_z, after.thorax_z)
            for field in ["tarsus5_z", "stumbling_contact_forces", "fly_heading"]:
                np.testing.assert_array_equal(getattr(before, field), getattr(after, field))
            drive = np.array([1.0, .8])
            original = reference.step(drive, before)
            optimized = cached.step(drive, after)
            np.testing.assert_array_equal(original.joint_angles, optimized.joint_angles)
            np.testing.assert_array_equal(original.adhesion_onoff, optimized.adhesion_onoff)
            apply_locomotion_action(sim, fly.name, optimized)
            sim.step()
