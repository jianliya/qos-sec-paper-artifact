from __future__ import annotations

from evaluation.registry import SCHEDULER_REGISTRY
from evaluation.sweep import run_scheduler_sweep


def run_baseline_comparison(jobs, backend_seed: int = 42):
    def scenario_builder():
        return jobs

    return run_scheduler_sweep(SCHEDULER_REGISTRY, scenario_builder, backend_seed=backend_seed)
