from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ArtifactStructureTests(unittest.TestCase):
    def test_required_artifact_paths_exist(self) -> None:
        required = (
            "configs/paper/timing_oext_wait_only_loso.json",
            "configs/paper/timing_osb.json",
            "configs/paper/timing_compile_awareness_oint.json",
            "configs/paper/timing_hardware.json",
            "reference_results/expected_metrics.json",
            "reference_results/results/timing_oext/wait_only_loso/summary_multiseed.json",
            "reference_results/results/timing/summary_multiseed_loso.json",
            "figures/published/figure2_timing_main.pdf",
        )
        for relative in required:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_primary_summary_has_seed_level_protocol(self) -> None:
        path = (
            ROOT
            / "reference_results/results/timing_oext/wait_only_loso/"
            / "summary_multiseed.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["num_seeds"], 16)
        self.assertEqual(
            payload["evaluation_protocol"]["split_mode"],
            "leave_one_seed_out",
        )
        self.assertEqual(
            payload["evaluation_protocol"]["observation_space"],
            "O_ext",
        )

    def test_source_modules_import_without_hardware_credentials(self) -> None:
        source_path = str(ROOT / "src")
        sys.path.insert(0, source_path)
        try:
            self.assertIsNotNone(
                importlib.util.find_spec("scenarios.legacy_timing_leakage")
            )
            self.assertIsNotNone(importlib.util.find_spec("cli.run_experiment"))
        finally:
            sys.path.remove(source_path)


if __name__ == "__main__":
    unittest.main()
