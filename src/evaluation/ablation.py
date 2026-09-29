from __future__ import annotations

from runtime.event_loop import EventLoop
from evaluation.runner import run_scenario
from evaluation.summaries import summarize_all
from scenarios.common import build_v2_backends
from scheduler.contention_robust_ext import ContentionRobustExtOrchestrator


ABLATIONS = {
    'full': dict(),
    'no_scarcity_awareness': {'enable_compatibility_awareness': False},
    'no_victim_protection': {'enable_sensitivity_protection': False},
    'no_pressure_budget': {'enable_pressure_budget': False},
    'no_fallback_cap': {'enable_fallback_cap': False},
}


def run_contention_robust_ablation(jobs, backend_seed: int = 42):
    results = {}
    for name, kwargs in ABLATIONS.items():
        scheduler = ContentionRobustExtOrchestrator(**kwargs)
        loop = EventLoop(build_v2_backends(seed=backend_seed), scheduler)
        lifecycle = run_scenario(loop, jobs)
        results[name] = summarize_all(jobs, lifecycle)
    return results
