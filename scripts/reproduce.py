from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CONFIG_DIR = ROOT / "configs" / "paper"
sys.path.insert(0, str(SRC))

from scenarios import timing_hardware, timing_leakage  # noqa: E402


def load_config(name: str) -> dict:
    path = CONFIG_DIR / name
    print(f"[artifact] config={path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_quick() -> None:
    cfg = load_config("timing_oext_wait_only_loso.json")
    result = timing_leakage.run_once(42, cfg)
    out = ROOT / "results" / "quick" / "summary_seed_42.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    expected = {
        "classA_mean_wait": 0.4529,
        "classB_mean_wait": 0.5064,
        "accuracy": 0.6318,
        "defended_accuracy": 0.5045,
        "defense_gain": 0.1273,
    }
    failures = []
    for key, value in expected.items():
        actual = float(result[key])
        state = "PASS" if round(actual, 4) == value else "FAIL"
        print(f"[{state}] {key}: actual={actual:.4f}, expected={value:.4f}")
        if state == "FAIL":
            failures.append(key)
    if failures:
        raise RuntimeError(f"quick reproduction mismatch: {', '.join(failures)}")
    print(f"[artifact] wrote {out.relative_to(ROOT)}")


def run_multiseed(config_name: str) -> None:
    timing_leakage.run_multiseed(load_config(config_name))


def run_function(config_name: str, function: Callable[[dict], object]) -> None:
    function(load_config(config_name))


def rq1_main() -> None:
    for name in (
        "timing_oext_wait_only_loso.json",
        "timing_oext_wait_status_loso.json",
        "timing_oext_wait_backend_loso.json",
        "timing_pair_width_matched_depth_diff_oext.json",
        "timing_pair_depth_matched_structure_diff_oext.json",
        "timing_pair_compile_divergent_oext.json",
    ):
        run_multiseed(name)


def rq1_aux() -> None:
    run_function("timing_probe_budget.json", timing_leakage.run_probe_budget)
    run_function(
        "timing_scheduler_comparison.json",
        timing_leakage.run_scheduler_oext_comparison,
    )
    run_function("timing_significance.json", timing_leakage.run_significance_analysis)


def rq2_boundary() -> None:
    run_multiseed("timing_osb.json")
    run_function(
        "timing_oext_release_tradeoff.json",
        timing_leakage.run_release_tradeoff,
    )
    run_function("timing_observability_ladder.json", timing_leakage.run_sweep)
    run_function("timing_paired_contrast.json", timing_leakage.run_paired_contrast)


def rq3_diagnostics() -> None:
    run_function(
        "timing_compile_awareness_oint.json",
        timing_leakage.run_compile_awareness,
    )
    run_function(
        "timing_compile_sweep.json",
        timing_leakage.run_compile_configuration_sweep,
    )
    run_function(
        "timing_noise_heterogeneity.json",
        timing_leakage.run_noise_heterogeneity,
    )
    run_function(
        "timing_controlled_pair_compile_stats.json",
        timing_leakage.run_controlled_pair_compile_stats,
    )


def appendix() -> None:
    run_function("timing_ablation.json", timing_leakage.run_ablation)
    run_function("timing_stability.json", timing_leakage.run_stability)
    run_function("timing_quantum_ablation.json", timing_leakage.run_quantum_ablation)


def rq4_hardware() -> None:
    if not os.environ.get("IBM_QUANTUM_TOKEN"):
        raise RuntimeError(
            "IBM_QUANTUM_TOKEN is not set; refusing to start a hardware run."
        )
    cfg = load_config("timing_hardware.json")
    result = timing_hardware.run_once(cfg)
    out = ROOT / "results" / "hardware" / "timing_hardware_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[artifact] wrote {out.relative_to(ROOT)}")


COMMANDS: dict[str, tuple[str, Callable[[], None]]] = {
    "quick": ("one deterministic seed-42 smoke reproduction", run_quick),
    "rq1-main": ("strict external views and controlled workload pairs", rq1_main),
    "rq1-aux": (
        "probe budget, scheduler comparison, and grouped significance",
        rq1_aux,
    ),
    "rq2-boundary": (
        "scheduler-boundary, release-control, and queue-control evidence",
        rq2_boundary,
    ),
    "rq3-diagnostics": (
        "compilation and backend-conditioned internal diagnostics",
        rq3_diagnostics,
    ),
    "appendix": ("ablation and repeated-seed robustness analyses", appendix),
    "rq4-hardware": (
        "explicit, quota-consuming public-backend feasibility run",
        rq4_hardware,
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run final paper evidence families without modifying frozen "
            "reference results."
        )
    )
    parser.add_argument("experiment", nargs="?", choices=sorted(COMMANDS))
    parser.add_argument(
        "--list",
        action="store_true",
        help="list experiment groups and exit",
    )
    args = parser.parse_args()
    if args.list:
        for name, (description, _) in COMMANDS.items():
            print(f"{name:16s} {description}")
        return 0
    if args.experiment is None:
        parser.error("choose an experiment or use --list")
    description, function = COMMANDS[args.experiment]
    print(f"[artifact] experiment={args.experiment}: {description}")
    function()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
