import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_neural_landing import NeuralLanding,BRAKE_S,DESCENT_S
from fly_leg_extension import DNP10_IDS
from fly_walking_navigation import WalkingNavigation


def metadata():
    return {"sensorimotor_candidates":[{"root_id":value,"population":"DNp10","side":side,
                                       "in_model":True,"ambiguous_type_correspondence":False}
                                      for side,value in DNP10_IDS.items()]}


def response(sequence,count):
    return {"brain_time_ms":sequence*10.,"sensorimotor_spikes":{DNP10_IDS["left"]:count,DNP10_IDS["right"]:0},
            "neuron_activity":{"sequence":sequence,"episode":0,"start_ms":(sequence-1)*10.,"end_ms":sequence*10.}}


class BrainLandingTests(unittest.TestCase):
    def test_hybrid_contact_stabilization_is_declared_and_legacy_is_unchanged(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        legacy=NeuralLanding(metadata())
        hybrid=NeuralLanding(metadata(),contact_stabilization=True)
        rotation=Rotation.from_euler("x",.1).as_matrix()
        for model in (legacy,hybrid):
            model.accept(response(1,1),True,[0,0,1],[15,0,0],0)
        np.testing.assert_array_equal(
            legacy.assistance(.001,.5,np.array([0,0,1.]),np.zeros(6),rotation),
            hybrid.assistance(.001,.5,np.array([0,0,1.]),np.zeros(6),rotation))
        for model in (legacy,hybrid):
            model.descent_start=.91
        old=legacy.assistance(.001,1.5,np.array([0,0,.2]),np.zeros(6),rotation)
        new=hybrid.assistance(.001,1.5,np.array([0,0,.2]),np.zeros(6),rotation)
        np.testing.assert_array_equal(old[:3],new[:3])
        np.testing.assert_allclose(new[3:],old[3:]*2.5)
        self.assertEqual(hybrid.snapshot()["descent_attitude_gain"],2000.)
        self.assertFalse(legacy.snapshot()["hybrid_contact_stabilization"])
        hybrid.touchdown_time=2.
        hybrid.release_time=3.
        hybrid.walk_navigation.begin([0,0,.1278],2.)
        np.testing.assert_array_equal(hybrid.assistance(.001,3.,np.array([0,0,.1278]),
                                                      np.zeros(6),rotation),np.zeros(6))

    def test_only_actual_current_flight_interval_can_initiate_request(self):
        model=NeuralLanding(metadata())
        self.assertFalse(model.accept(response(1,0),True,[0,0,1],[15,0,0],0))
        self.assertFalse(model.accept(response(2,2),False,[0,0,1],[15,0,0],0))
        self.assertIsNone(model.request_time)
        self.assertTrue(model.accept(response(3,1),True,[0,0,1],[15,0,0],0))
        self.assertEqual(model.request["interval_spikes"],1)
        self.assertEqual(model.request["sequence"],3)
        self.assertEqual(model.request["time_s"],.03)
        self.assertFalse(model.accept(response(4,2),True,[0,0,1],[15,0,0],0))
        self.assertEqual(model.request["sequence"],3)
        with self.assertRaises(ValueError):
            model.accept(response(4,2),True,[0,0,1],[15,0,0],0)

    def test_reference_continuity_stable_contact_and_assistance_release(self):
        import numpy as np
        model=NeuralLanding(metadata())
        model.accept(response(1,1),True,[0,0,1],[15,0,0],0)
        position,velocity,_=model.reference(.01)
        self.assertEqual(position,[0,0,1])
        self.assertEqual(velocity,[15,0,0])
        self.assertAlmostEqual(model.reference(.01+BRAKE_S)[1][0],0)
        self.assertEqual(model.reference(.01+BRAKE_S+DESCENT_S)[0][2],1.)
        model.observe(.81,0,.95,0.,[2,0,1])
        model.observe(.91,0,.95,0.,[2,0,1])
        self.assertAlmostEqual(model.reference(.91+DESCENT_S)[0][2],.1278)
        self.assertEqual(model.snapshot()["descent_duration_s"],.75)
        for step in range(100):
            model.observe(1.81+step*.002,1,.95,0.,[2,0,.1278])
        self.assertIsNone(model.touchdown_time)
        for step in range(110):
            model.observe(2.1+step*.002,1,.95,0.,[2,0,.1278])
        self.assertIsNotNone(model.touchdown_time)
        timestamp=2.318
        while timestamp<model.release_time:
            timestamp=min(model.release_time,timestamp+.002)
            model.observe(timestamp,1,.95,2,[2,0,.1278])
        force=model.assistance(.001,model.release_time,[2,0,.1278],np.zeros(6),np.eye(3))
        np.testing.assert_array_equal(force,np.zeros(6))
        self.assertEqual(model.phase(model.release_time),"post-landing-walk")
        self.assertGreaterEqual(model.stable_walk_steps,1)
        model.observe(model.release_time+.0002,0,.95,2,[2,0,.1278])
        self.assertEqual(model.stable_walk_steps,0)

    def test_between_cycle_motor_reset_preserves_neural_sequence(self):
        model=NeuralLanding(metadata())
        model.accept(response(1,1),True,[0,0,1],[15,0,0],0)
        model.reset(clear_neural=False)
        self.assertIsNone(model.request)
        self.assertTrue(model.accept(response(2,1),True,[0,0,1],[15,0,0],0))
        model.reset()
        self.assertEqual(model.decoder.sequence,0)

    def test_walking_reference_curves_before_boundary_without_pose_updates(self):
        model=WalkingNavigation(11.25)
        model.begin([0,0,.1278],0)
        position=[0,0,.1278]
        for step in range(2500):
            model.update(position,step*.01)
            position,_,yaw=model.reference(step*.01+.01)
            self.assertLess(max(abs(v) for v in position[:2]),10.75)
        self.assertGreater(abs(yaw),.5)
