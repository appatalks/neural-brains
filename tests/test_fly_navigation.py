import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_navigation import FlightNavigation, landing_assistance
from fly_flight_app import cycle_test_passed


class EngineeredNavigationTests(unittest.TestCase):
    def test_orbit_is_continuous_at_launch_transition_and_curves(self):
        navigation=FlightNavigation(15)
        navigation.begin([0,0,.1278],0)
        first=navigation.reference(.3)
        self.assertEqual(first[0],[6,0,1])
        second=navigation.reference(.300001)
        self.assertLess(math.dist(first[0],second[0]),.0001)
        self.assertNotEqual(navigation.reference(.5)[0][1],0)
        for i in range(1000):
            position,velocity,_=navigation.reference(i*.01)
            self.assertLess(max(abs(v) for v in position[:2]),15)
            self.assertAlmostEqual(math.hypot(*velocity[:2]),20)

    def test_descent_is_continuous_and_stops_at_ground_reference(self):
        navigation=FlightNavigation(15)
        navigation.begin([0,0,.1278],0)
        navigation.request_landing([4,3,1],1)
        self.assertEqual(navigation.reference(1)[0],[4,3,1])
        self.assertEqual(navigation.reference(3)[0],[4,3,.1278])
        navigation.request_landing([9,9,9],2)
        self.assertEqual(navigation.landing_origin,[4,3,1])

    def test_landing_force_and_torque_are_finite_with_gravity_compensation(self):
        import numpy as np
        result=landing_assistance(.001,np.array([0.,0,1]),np.zeros(6),np.eye(3),[0,0,1])
        np.testing.assert_allclose(result,[0,0,.981,0,0,0])

    def test_cycle_does_not_pass_for_touchdown_without_unassisted_walk(self):
        summary={
            "status":"completed","same_body_mass_inertia_unchanged":True,
            "initial_ground_contact_observed":True,"handoffs":[{"qpos_preserved":True,"qvel_preserved":True}],
            "flight_steps":3000,"flight_floor_contact_steps":0,"safety_stopped":False,
            "landed_at_s":3,"stable_unassisted_post_landing_steps":0,
        }
        self.assertFalse(cycle_test_passed(summary))
        self.assertTrue(cycle_test_passed({**summary,"stable_unassisted_post_landing_steps":1500}))

    def test_unstarted_navigation_and_invalid_arena_rejected(self):
        with self.assertRaises(ValueError):
            FlightNavigation(15).reference(1)
        with self.assertRaises(ValueError):
            FlightNavigation(float("nan"))
