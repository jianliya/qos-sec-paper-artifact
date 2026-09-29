from __future__ import annotations

from evaluation.compare_baselines import run_baseline_comparison


def summarize_tradeoff(results: dict):
    tradeoff = {}
    for scheduler_name, summary in results.items():
        system_metrics = summary['system_metrics']
        victim_metrics = summary.get('victim_metrics', {})
        attacker_metrics = summary.get('attacker_metrics', {})
        tradeoff[scheduler_name] = {
            'victim_mean_wait': victim_metrics.get('victim_mean_wait', 0.0),
            'victim_p99_wait': victim_metrics.get('victim_p99_wait', 0.0),
            'victim_slowdown_ratio': victim_metrics.get('victim_slowdown_ratio', 0.0),
            'attacker_mean_turnaround': attacker_metrics.get('attacker_mean_turnaround', 0.0),
            'attacker_DPR_A': attacker_metrics.get('DPR_A', 0.0),
            'attacker_effective_service': attacker_metrics.get('attacker_effective_service', 0.0),
            'system_mean_turnaround': system_metrics.get('mean_turnaround', 0.0),
            'throughput': system_metrics.get('throughput', 0.0),
            'wait_fairness': system_metrics.get('wait_fairness', 0.0),
            'worst_tenant_degradation': system_metrics.get('worst_tenant_degradation', 0.0),
            'fidelity_proxy_cost': system_metrics.get('fidelity_proxy_cost', 0.0),
        }
    return tradeoff


def run_tradeoff(scenario_builder):
    results = run_baseline_comparison(scenario_builder())
    return summarize_tradeoff(results)
