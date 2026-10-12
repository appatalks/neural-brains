import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from vnc_reference import integrate, START_S, MOTOR_BODY_ID
from test_bdn2_vnc import parameters


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Existing numerical environment required")
class IndependentReferenceTests(unittest.TestCase):
    def fixture(self):
        import numpy as np
        weights = np.zeros((5, 5))
        weights[0, 4] = 100.
        return weights, parameters(np.ones(5))

    def test_onset_silence_and_actual_output_clamp(self):
        import numpy as np
        weights, params = self.fixture()
        times, rates = integrate(weights, params, 4, "intact")
        self.assertEqual(rates.shape, (5, 1001))
        self.assertEqual(times[-1], 1.)
        self.assertGreater(rates[4].max(), 0)
        np.testing.assert_array_equal(rates[:, times <= START_S], np.zeros_like(rates[:, times <= START_S]))
        for case in ("no-drive", "dn-cut", "mn-silence"):
            _, observed = integrate(weights, params, 4, case)
            np.testing.assert_array_equal(observed[4], np.zeros(1001))
            if case != "no-drive":
                self.assertGreater(observed[0].max(), 0)

    def test_cross_integrator_convergence_and_exact_replay(self):
        import numpy as np
        weights, params = self.fixture()
        _, first = integrate(weights, params, 4, "intact")
        _, replay = integrate(weights, params, 4, "sham")
        _, alternate = integrate(weights, params, 4, "intact", "DOP853")
        np.testing.assert_array_equal(first, replay)
        self.assertLess(np.max(np.abs(first-alternate)), .001)

    def test_invalid_solver_output_index_or_parameters_fail(self):
        import numpy as np
        weights, params = self.fixture()
        for kwargs in ({"case": "invented"}, {"motor": 0}, {"method": "unapproved"},
                       {"tolerance": .01}):
            arguments = {"weights": weights, "params": params, "motor": 4, "case": "intact", **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                integrate(**arguments)
        params["tau"][0] = np.nan
        with self.assertRaises(ValueError):
            integrate(weights, params, 4, "intact")
        self.assertEqual(MOTOR_BODY_ID, "12686")
