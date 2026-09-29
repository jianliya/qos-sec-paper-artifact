from __future__ import annotations

from runtime.event_loop import EventLoop
from evaluation.runner import run_scenario
from evaluation.summaries import summarize_all
from scenarios.common import build_v2_backends


def run_scheduler_sweep(scheduler_classes, scenario_builder, backend_seed: int = 42):
    results = {}
    for name, scheduler_cls in scheduler_classes.items():
        jobs = scenario_builder()
        loop = EventLoop(build_v2_backends(seed=backend_seed), scheduler_cls())
        lifecycle = run_scenario(loop, jobs)
        results[name] = summarize_all(jobs, lifecycle)
    return results
