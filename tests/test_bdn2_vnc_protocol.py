import importlib.util
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from test_bdn2_vnc import parameters, rate_derivative, retained_weight_indices, rhythm_passed, run, run_archived, simulate, simulate_diffrax


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Existing numerical simulation environment required")
class VncProtocolTests(unittest.TestCase):
    def test_default_protocol_is_saved_before_numerical_failure_without_archive_mode_flags(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/"result"
            fixture = (np.zeros((4, 4)), [{"bodyId": str(index)} for index in range(4)],
                       np.ones(4), 1., {})
            with patch("test_bdn2_vnc.load_circuit", return_value=fixture), patch(
                "test_bdn2_vnc.simulate", side_effect=RuntimeError("synthetic numerical failure")
            ), patch("builtins.print"):
                with self.assertRaisesRegex(RuntimeError, "Predeclared"):
                    run(Path(temporary)/"data", output)
            protocol = json.loads((output/"protocol.json").read_text())
            self.assertEqual(len(protocol["predeclared_checks"]), 6)
            self.assertEqual(json.loads((output/"status.json").read_text())["status"], "failed")
            self.assertEqual(len(json.loads((output/"results.json").read_text())), 28)

    def test_invalid_archived_solver_mode_combinations_fail_before_asset_access(self):
        for kwargs in ({"solver": "scipy", "dense_parent": True},
                       {"solver": "scipy", "full_network": True},
                       {"solver": "diffrax", "full_network": True, "all_motor_targets": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_archived(Path("/unused/data"), Path("/unused/result"), **kwargs)

    def test_actual_weight_mask_keeps_silent_motor_targets_not_only_active_outputs(self):
        import numpy as np
        mask = np.zeros((8, 8), dtype=bool)
        retained = np.array([0, 1, 2, 3, 5, 7])
        mask[np.ix_(retained, retained)] = True
        activity = np.array([True, True, True, True, False, True, False, False])
        result = retained_weight_indices(mask, np.arange(4))
        np.testing.assert_array_equal(result, retained)
        self.assertIn(7, result)
        self.assertFalse(activity[7])
        with self.assertRaises(ValueError):
            retained_weight_indices(mask.astype(float), np.arange(4))
        with self.assertRaises(ValueError):
            retained_weight_indices(mask, np.array([0, 1, 2, 4]))

    def test_parameter_volume_scaling_and_seed_replay(self):
        import numpy as np
        params = parameters(np.array([1., 2.]), reference_size=1.)
        np.testing.assert_array_equal(params["gain"], [1., .5])
        np.testing.assert_array_equal(params["threshold"], [7.5, 15.])
        first = parameters(np.array([1., 2.]), 427, 1.)
        replay = parameters(np.array([1., 2.]), 427, 1.)
        for name in first:
            np.testing.assert_array_equal(first[name], replay[name])
            self.assertTrue((first[name] > 0).all())
        for sizes, reference in (([1, 0], 1.), ([1, float("nan")], 1.), ([1, 2], 0.)):
            with self.assertRaises(ValueError):
                parameters(np.array(sizes), reference_size=reference)

    def test_directional_rate_equation_preserves_inhibitory_effect(self):
        import numpy as np
        params = {name: np.array(values) for name, values in {
            "tau": [.02, .02], "gain": [1., 1.], "cap": [200., 200.],
            "threshold": [7.5, 7.5],
        }.items()}
        state = np.array([20., 5.])
        applied = np.array([0., 0.])
        weights = np.array([[0., 0.], [2., 0.]])
        positive = rate_derivative(state, applied, weights, params)
        negative = rate_derivative(state, applied, -weights, params)
        self.assertGreater(positive[1], negative[1])
        self.assertAlmostEqual(negative[1], -5/.02)
        np.testing.assert_array_equal(rate_derivative(np.zeros(2), applied, weights, params), [0., 0.])

    def test_zero_drive_and_disconnection_are_actual_dynamics(self):
        import numpy as np
        weights = np.zeros((4, 4))
        weights[0, 1] = 187
        params = parameters(np.ones(4))
        times, silent = simulate(weights, params, "no-drive", duration=1.)
        self.assertEqual(silent.shape, (4, 1001))
        self.assertEqual(times[-1], 1.)
        np.testing.assert_array_equal(silent, np.zeros_like(silent))
        _, cut = simulate(weights, params, "dn-cut", duration=1.)
        self.assertGreater(cut[0].max(), 0)
        np.testing.assert_array_equal(cut[1:], np.zeros_like(cut[1:]))
        with self.assertRaises(ValueError):
            simulate(weights, params, "undeclared")

    def test_motor_rhythm_gate_does_not_accept_core_only_or_in_phase_output(self):
        row = {"modules": {
            "coxa swing": {"peak_count": 5, "peak_to_peak_rate": 2.},
            "coxa stance": {"peak_count": 5, "peak_to_peak_rate": 2.},
        }, "swing_stance_correlation": -.5}
        self.assertTrue(rhythm_passed(row))
        self.assertFalse(rhythm_passed({**row, "swing_stance_correlation": .9}))
        self.assertFalse(rhythm_passed({**row, "swing_stance_correlation": None}))
        row["modules"]["coxa stance"]["peak_count"] = 0
        self.assertFalse(rhythm_passed(row))


@unittest.skipUnless(importlib.util.find_spec("jax") and importlib.util.find_spec("diffrax"),
                     "Approved isolated VNC environment required")
class NativeVncSolverTests(unittest.TestCase):
    def fixture(self):
        import numpy as np
        weights = np.zeros((4, 4))
        weights[0, 1] = 187
        local = parameters(np.ones(4))
        parent = {name: np.full(4604, value[0]) for name, value in local.items()}
        return weights, local, np.arange(4), parent

    def test_native_zero_drive_and_source_disconnection_preserve_silent_states(self):
        import numpy as np
        weights, local, indices, parent = self.fixture()
        times, rates, diagnostics = simulate_diffrax(weights, local, "no-drive", indices, parent)
        self.assertEqual(rates.shape, (4, 1001))
        self.assertEqual(times[-1], 1.)
        self.assertEqual(rates.dtype, np.float32)
        np.testing.assert_array_equal(rates, np.zeros_like(rates))
        self.assertEqual(diagnostics["negative_sample_count"], 0)
        self.assertIn("postprocessing", diagnostics)
        _, rates, _ = simulate_diffrax(weights, local, "dn-cut", indices, parent)
        self.assertGreater(rates[0].max(), 0)
        np.testing.assert_array_equal(rates[1:], np.zeros_like(rates[1:]))

    def test_invalid_native_parameters_and_parent_mapping_fail_before_integration(self):
        import numpy as np
        for case in ("duplicate", "missing", "nonfinite", "mismatch", "nonpositive"):
            weights, local, indices, parent = self.fixture()
            if case == "duplicate":
                indices[1] = 0
            elif case == "missing":
                local.pop("cap")
            elif case == "nonfinite":
                weights[0, 1] = np.nan
            elif case == "mismatch":
                parent["gain"][0] = 2.
            else:
                parent["tau"][0] = 0.
            with self.subTest(case=case), self.assertRaises(ValueError):
                simulate_diffrax(weights, local, "intact", indices, parent)
