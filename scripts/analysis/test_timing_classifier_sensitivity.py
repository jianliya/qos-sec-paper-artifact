from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("timing_classifier_sensitivity.py")
SPEC = importlib.util.spec_from_file_location("timing_classifier_sensitivity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TimingClassifierSensitivityTests(unittest.TestCase):
    def test_logistic_separates_simple_training_data(self) -> None:
        features = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
        labels = np.asarray([0.0, 0.0, 1.0, 1.0])
        weights, bias = MODULE._fit_logistic(features, labels, "logistic")
        scores = features @ weights + bias
        self.assertTrue(np.all(scores[:2] < 0.0))
        self.assertTrue(np.all(scores[2:] >= 0.0))

    def test_quadratic_design_is_fixed_and_two_dimensional(self) -> None:
        values = np.asarray([[-2.0], [3.0]])
        design = MODULE._design(values, "quadratic_logistic")
        np.testing.assert_array_equal(design, np.asarray([[-2.0, 4.0], [3.0, 9.0]]))

    def test_student_t_summary_contains_mean(self) -> None:
        summary = MODULE._summary([0.5, 0.6, 0.7, 0.8])
        self.assertAlmostEqual(summary["mean"], 0.65)
        self.assertGreater(summary["ci95_half_width"], 0.0)


if __name__ == "__main__":
    unittest.main()
