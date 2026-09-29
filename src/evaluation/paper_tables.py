from __future__ import annotations

from pathlib import Path
import csv


def export_paper_main_table(results: dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'scenario', 'scheduler', 'victim_wait', 'victim_p99_wait', 'victim_slowdown',
            'attacker_DPR_A', 'attacker_effective_service',
            'system_turnaround', 'throughput', 'fairness', 'worst_tenant_degradation', 'fidelity_proxy_cost'
        ])
        for scenario_name, scenario_result in results.items():
            for scheduler_name, summary in scenario_result.items():
                writer.writerow([
                    scenario_name,
                    scheduler_name,
                    summary.get('victim_metrics', {}).get('victim_mean_wait', 0.0),
                    summary.get('victim_metrics', {}).get('victim_p99_wait', 0.0),
                    summary.get('victim_metrics', {}).get('victim_slowdown_ratio', 0.0),
                    summary.get('attacker_metrics', {}).get('DPR_A', 0.0),
                    summary.get('attacker_metrics', {}).get('attacker_effective_service', 0.0),
                    summary.get('system_metrics', {}).get('mean_turnaround', 0.0),
                    summary.get('system_metrics', {}).get('throughput', 0.0),
                    summary.get('system_metrics', {}).get('wait_fairness', 0.0),
                    summary.get('system_metrics', {}).get('worst_tenant_degradation', 0.0),
                    summary.get('system_metrics', {}).get('fidelity_proxy_cost', 0.0),
                ])
