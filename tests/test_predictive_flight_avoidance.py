import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from fly_flight_avoidance import FlightAvoidance, MAX_TURN_RAD_S, MAX_TURN_ACCEL_RAD_S2, MIN_HALF_SIZE_CM


class FlightAvoidanceTests(unittest.TestCase):
    def test_off_center_launch_preserves_heading_and_limits_outward_travel(self):
        controller=FlightAvoidance(11.25)
        controller.begin([6.75,9.65,.13],0.,math.pi/2,launch=True)
        self.assertEqual(controller.yaw,math.pi/2)
        self.assertEqual(controller.speed,0.)
        original=[6.75,9.65,.13]
        for step in range(30):
            controller.update(original,step*.01,[])
            self.assertEqual(controller.speed,0.)
        self.assertNotEqual(controller.turn_rate,0.)
        self.assertEqual(original,[6.75,9.65,.13])
        self.assertTrue(controller.snapshot()["launch_clearance_guard"])

    def test_launch_assistance_uses_reference_velocity_not_world_x(self):
        import numpy as np
        from fly_takeoff import assisted_force
        position=np.array([1.,2.,1.])
        force=assisted_force(.001,position,np.zeros(6),np.eye(3),np.eye(3),position,[0.,5.,0.])
        np.testing.assert_allclose(force[:3],[0.,.5,.981])
        held=assisted_force(.001,position,np.zeros(6),np.eye(3),np.eye(3),position,[0.,0.,0.])
        np.testing.assert_allclose(held[:3],[0.,0.,.981])
        with self.assertRaises(ValueError):
            assisted_force(.001,position,np.zeros(6),np.eye(3),np.eye(3),position,[float("nan"),0,0])

    def test_invalid_initialization_and_noncontiguous_clock_fail(self):
        for half in (3,MIN_HALF_SIZE_CM-.01,float("nan")):
            with self.assertRaises(ValueError):
                FlightAvoidance(half)
        controller=FlightAvoidance(15)
        with self.assertRaises(ValueError):
            controller.reference(0)
        controller.begin([0,0,1],0)
        for timestamp in (-.1,.02,float("nan")):
            with self.assertRaises(ValueError):
                controller.update([0,0,1],timestamp,[])
        with self.assertRaises(ValueError):
            controller.update([0,0,1],0,[{"position_cm":[float("nan"),0,0]}])
        with self.assertRaises(ValueError):
            controller.reference(.1)

    def test_half_area_reference_is_slower_and_stays_inside(self):
        controller=FlightAvoidance(MIN_HALF_SIZE_CM)
        self.assertAlmostEqual(controller.cruise_speed,15/math.sqrt(2))
        position=[0.,0.,1.]
        controller.begin(position,0.)
        for step in range(1000):
            controller.update(position,step*.01,[])
            position,_,_=controller.reference(step*.01+.01)
            self.assertGreater(controller.half-max(abs(v) for v in position[:2]),.5)

    def test_turns_before_boundary_with_bounded_continuous_reference(self):
        controller=FlightAvoidance(15)
        controller.begin([0,0,1],0)
        previous=controller.reference(0)[0]
        previous_rate=0.
        for step in range(500):
            t=step*.01
            controller.update(previous,t,[])
            target,velocity,yaw=controller.reference(t+.01)
            self.assertLess(math.dist(target,previous),.201)
            self.assertLessEqual(abs(controller.turn_rate),MAX_TURN_RAD_S)
            self.assertLessEqual(abs(controller.turn_rate-previous_rate),MAX_TURN_ACCEL_RAD_S2*.01+1e-9)
            self.assertAlmostEqual(math.hypot(*velocity[:2]),20.)
            self.assertGreater(15-max(abs(v) for v in target[:2]),.5)
            previous,previous_rate=target,controller.turn_rate
        self.assertGreater(controller.commands,0)
        self.assertGreater(abs(yaw),2*math.pi)

    def test_measured_position_changes_planning_not_an_unconditional_orbit(self):
        a,b=FlightAvoidance(15),FlightAvoidance(15)
        for controller in (a,b):
            controller.begin([0,0,1],0)
        for step in range(1,30):
            a.update([0,0,1],step*.01,[])
            b.update([0,0,1],step*.01,[{"position_cm":[5,-2,1]}])
        self.assertNotEqual(a.turn_rate,b.turn_rate)
        b.reset()
        self.assertIsNone(b.start)
        self.assertFalse(b.commands)
