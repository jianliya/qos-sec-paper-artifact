from __future__ import annotations

from statistics import mean

from runtime.event_loop import EventLoop
from evaluation.runner import run_scenario
from evaluation.summaries import summarize_all
from scenarios.common import build_v2_backends


def run_multiseed(scheduler_cls, scenario_builder, seeds):
    runs = []
    for seed in seeds:
        jobs = scenario_builder()
        loop = EventLoop(build_v2_backends(seed=seed), scheduler_cls())
        lifecycle = run_scenario(loop, jobs)
        runs.append(summarize_all(jobs, lifecycle))

    system_waits = [r['system_metrics']['mean_wait'] for r in runs]
    system_turns = [r['system_metrics']['mean_turnaround'] for r in runs]
    return {
        'seeds': list(seeds),
        'runs': runs,
        'aggregate': {
            'mean_system_wait': mean(system_waits) if system_waits else 0.0,
            'mean_system_turnaround': mean(system_turns) if system_turns else 0.0,
        },
    }
