import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import test_vnc_joint as joint


class AssumedJointInterfaceTests(unittest.TestCase):
    def test_activation_has_exact_zero_rest_and_declared_exponential_withdrawal(self):
        self.assertEqual(joint.activation_step(0., 0., .001), 0.)
        self.assertAlmostEqual(joint.activation_step(.5, 0., .06), .5*math.exp(-1))
        activation = joint.activation_step(0., 10., .06)
        self.assertAlmostEqual(activation, .5*(1-math.exp(-1)))
        for arguments in ((-.1, 0., .001), (.5, -1., .001), (0., 1., 0.), (0., math.nan, .001)):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                joint.activation_step(*arguments)

    def test_feedback_removal_is_not_neural_output_fabrication(self):
        no_feedback, drive, correction = joint.torque_command(.2, .1, .1, False)
        self.assertEqual(correction, 0)
        self.assertEqual(no_feedback, drive)
        with_feedback, same_drive, correction = joint.torque_command(.2, .1, .1, True)
        self.assertEqual(same_drive, drive)
        self.assertNotEqual(with_feedback, no_feedback)
        self.assertLess(correction, 0)
        self.assertEqual(abs(joint.torque_command(1., -100., -100., True)[0]), joint.MAX_TORQUE)
        with self.assertRaises(ValueError):
            joint.torque_command(.5, math.nan, 0., True)

    def manifest(self):
        variants = ["saved-336", "saved-422", "prospective-429"]
        ids = [str(100+index) for index in range(148)]
        ids[4] = joint.MOTOR_BODY_ID
        protocol = {"schema_version": 1, "reference_kind": "independent-event-resolved-float64",
                    "variants": variants, "body_ids": ids, "motor_index": 4,
                    "motor_body_id": joint.MOTOR_BODY_ID, "duration_s": 1., "sample_dt_s": .001,
                    "prospective_parameter_seed": 429}
        checks = [
            {"variant": variant, "case": case, "passed": True, "maximum_rate_difference": 0.}
            for variant in variants
            for case in (*joint.REFERENCE_CASES, "independent-integrator", "tighter-tolerance", "fresh-reset-replay")
        ]
        return protocol, {"status": "passed", "checks": checks}

    def test_reference_requires_complete_control_results_and_exact_cell_order(self):
        protocol, validation = self.manifest()
        joint.validate_reference_manifest(protocol, validation)
        for case in ("empty", "duplicate", "motor", "convergence", "boolean", "path"):
            p, v = copy.deepcopy(protocol), copy.deepcopy(validation)
            if case == "empty":
                v["checks"] = []
            elif case == "duplicate":
                v["checks"][-1] = v["checks"][0]
            elif case == "motor":
                p["body_ids"][4] = "unverified"
            elif case == "convergence":
                next(row for row in v["checks"] if row["case"] == "independent-integrator")["maximum_rate_difference"] = .1
            elif case == "boolean":
                p["schema_version"] = True
            else:
                p["variants"][2] = "../unverified"
            with self.subTest(case=case), self.assertRaises(ValueError):
                joint.validate_reference_manifest(p, v)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "Numerical environment required")
    def test_small_accepted_roundoff_is_reported_and_raw_reference_is_preserved(self):
        import numpy as np
        raw = np.zeros(1001)
        raw[132] = -2.483e-9
        with patch("builtins.print") as warning:
            normalized, diagnostics = joint.physical_rate_trace(raw)
        self.assertEqual(diagnostics["negative_roundoff_samples"], 1)
        self.assertEqual(normalized[132], 0.)
        self.assertLess(raw[132], 0.)
        warning.assert_called_once()
        for invalid in (-1e-5, np.nan):
            raw[132] = invalid
            with self.assertRaises(ValueError):
                joint.physical_rate_trace(raw)

    @unittest.skipUnless(importlib.util.find_spec("dm_control"), "Pinned FlyBody environment required")
    def test_actual_bench_preserves_mass_and_uses_only_one_direct_torque_actuator(self):
        import mujoco as mj
        import numpy as np
        model, data, actuator, metadata = joint.make_bench()
        self.assertTrue(metadata["original_mass_inertia_preserved"])
        self.assertEqual(model.actuator_gainprm[actuator, 0], 1.)
        self.assertEqual(np.count_nonzero(model.actuator_gainprm[:, 0]), 1)
        self.assertFalse(model.actuator_biasprm.any())
        self.assertEqual(model.actuator_dyntype[actuator], mj.mjtDyn.mjDYN_NONE)
        self.assertEqual(model.eq_type[model.equality("joint_probe_fixture").id], mj.mjtEq.mjEQ_WELD)
        self.assertFalse(data.xfrc_applied.any())
        data.ctrl[actuator] = .0001
        mj.mj_step(model, data)
        self.assertAlmostEqual(data.actuator_force[actuator], .0001)
