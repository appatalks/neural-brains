import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import fly_flight_app
import fly_habitat
from fly_dashboard import DEFAULT_PORT, validate_app_port


class FlightAppTests(unittest.TestCase):
    def test_one_browser_port_is_enforced_before_model_loading(self):
        self.assertEqual(DEFAULT_PORT,8840)
        self.assertEqual(validate_app_port(DEFAULT_PORT),DEFAULT_PORT)
        for port in (0,8841,True,-1,"8840"):
            with self.subTest(port=port),self.assertRaises(ValueError):
                validate_app_port(port)
            with self.assertRaises(ValueError):
                fly_flight_app.run(Path("/unused"),Path("/unused"),Path("/unused"),Path("/unused"),port=port)
        for port in ("0","8841"):
            with self.assertRaises(SystemExit):
                fly_habitat.main(["--data-dir","/unused","--output-dir","/unused","--dashboard-port",port])

    def test_flight_requires_preserved_state_sustained_airborne_and_no_safety_stop(self):
        summary={
            "status":"completed","same_body_mass_inertia_unchanged":True,
            "initial_ground_contact_observed":True,
            "handoffs":[{"qpos_preserved":True,"qvel_preserved":True}],
            "flight_steps":2500,"flight_floor_contact_steps":0,"safety_stopped":False,
        }
        self.assertTrue(fly_flight_app.flight_test_passed(summary))
        for key,value in [
            ("status","safety_stopped"),("same_body_mass_inertia_unchanged",False),
            ("initial_ground_contact_observed",False),("handoffs",[]),
            ("handoffs",[{"qpos_preserved":True,"qvel_preserved":False}]),
            ("flight_steps",2499),("flight_floor_contact_steps",1),("safety_stopped",True),
        ]:
            with self.subTest(key=key):
                self.assertFalse(fly_flight_app.flight_test_passed({**summary,key:value}))
    def test_main_launcher_uses_isolated_flight_environment(self):
        with patch("fly_habitat.subprocess.run",return_value=SimpleNamespace(returncode=0)) as run:
            result=fly_habitat.main([
                "--backend","unified","--data-dir","/external/data","--output-dir","/external/run",
                "--objects","/external/objects.json","--seconds","1.5",
            ])
        self.assertEqual(result,0)
        command=run.call_args.args[0]
        self.assertEqual(command[:2],[str(ROOT/".venv-flight/bin/python"),str(ROOT/"scripts/fly_flight_app.py")])
        self.assertIn("--objects",command)
        self.assertIn("--seconds",command)
        self.assertEqual(command[command.index("--arena-half-size-mm")+1],"112.5")
        self.assertEqual(command[command.index("--scene")+1],str(ROOT/"experiments/fly-walking/grassland-habitat.json"))
        self.assertEqual(command[command.index("--feeding-config")+1],str(ROOT/"experiments/flywire-sugar/grassland-feeding.json"))
        self.assertNotIn("--test-stimulus",command)
        self.assertNotIn("--neural-leg-extension",command)
        self.assertNotIn("--graded-vision",command)
        self.assertNotIn("--flight-avoidance",command)

    def test_reduced_neural_extension_is_explicit_and_unified_only(self):
        with patch("fly_habitat.subprocess.run",return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(fly_habitat.main([
                "--backend","unified","--data-dir","/external/data","--output-dir","/external/run",
                "--neural-leg-extension",
            ]),0)
        self.assertIn("--neural-leg-extension",run.call_args.args[0])
        with self.assertRaises(SystemExit):
            fly_habitat.main(["--data-dir","/external/data","--output-dir","/external/run",
                              "--neural-leg-extension"])

    def test_graded_vision_is_explicit_and_unified_only(self):
        with patch("fly_habitat.subprocess.run",return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(fly_habitat.main([
                "--backend","unified","--data-dir","/external/data","--output-dir","/external/run",
                "--graded-vision",
            ]),0)
        self.assertIn("--graded-vision",run.call_args.args[0])
        with self.assertRaises(SystemExit):
            fly_habitat.main(["--data-dir","/external/data","--output-dir","/external/run","--graded-vision"])

    def test_flight_avoidance_is_explicit_and_preserves_baseline(self):
        with patch("fly_habitat.subprocess.run",return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(fly_habitat.main([
                "--backend","unified","--data-dir","/external/data","--output-dir","/external/run",
                "--flight-avoidance",
            ]),0)
        self.assertIn("--flight-avoidance",run.call_args.args[0])
        with self.assertRaises(SystemExit):
            fly_habitat.main(["--data-dir","/external/data","--output-dir","/external/run","--flight-avoidance"])

    def test_invalid_explicit_test_modes_fail_before_loading_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            for kwargs in [{"test_stimulus":True},{"test_approach":True},
                           {"test_stimulus":True,"test_approach":True,"seconds":1.5},
                           {"neural_leg_extension":True,"engineered_navigation":True},
                           {"flight_avoidance":True,"engineered_navigation":True},
                           {"flight_avoidance":True,"arena_half_size_mm":30},
                           {"brain_linked_landing":True,"engineered_navigation":True},
                           {"landing_surface_vision":True},
                           {"research_dnp10":"silence","brain_linked_landing":True},
                           {"controlled_test":True},
                           {"test_leg_extension":True,"seconds":1.2}]:
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                    fly_flight_app.run(
                        Path(temporary)/"data",Path(temporary)/"run",Path("/unused"),Path("/unused"),**kwargs,
                    )

    def test_brain_landing_options_are_explicit_and_preserve_binary_comparison(self):
        with patch("fly_habitat.subprocess.run",return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(fly_habitat.main([
                "--backend","unified","--data-dir","/external/data","--output-dir","/external/run",
                "--brain-linked-landing","--landing-surface-vision",
            ]),0)
        self.assertIn("--brain-linked-landing",run.call_args.args[0])
        self.assertIn("--landing-surface-vision",run.call_args.args[0])
        self.assertNotIn("--research-dnp10",run.call_args.args[0])

    def test_invalid_arena_and_inside_repository_output_rejected(self):
        with self.assertRaises(ValueError):
            fly_flight_app.run(Path("/external"),ROOT/"results",Path("/unused"),Path("/unused"))
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                fly_flight_app.run(Path(temporary)/"data",Path(temporary)/"run",Path("/unused"),Path("/unused"),
                                   arena_half_size_mm=20)
