from __future__ import annotations

from pathlib import Path
import csv
import json

from evaluation.main_experiment import run_main_experiment
from evaluation.ablation import run_contention_robust_ablation
from evaluation.tradeoff import run_tradeoff
from scenarios.contention_heavy import build_scenario as heavy


def export_main_summary(output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_main_experiment(output_dir / 'main_experiment')

    summary_csv = output_dir / 'paper_main_summary.csv'
    with summary_csv.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'scenario', 'scheduler',
            'victim_mean_wait', 'victim_p95_wait', 'victim_p99_wait', 'victim_slowdown_ratio',
            'attacker_mean_turnaround', 'attacker_DPR_A', 'attacker_effective_service',
            'system_mean_wait', 'system_mean_turnaround', 'throughput',
            'wait_fairness', 'worst_tenant_degradation', 'fidelity_proxy_cost'
        ])
        for scenario_name, scenario_result in results.items():
            for scheduler_name, summary in scenario_result.items():
                writer.writerow([
                    scenario_name,
                    scheduler_name,
                    summary.get('victim_metrics', {}).get('victim_mean_wait', 0.0),
                    summary.get('victim_metrics', {}).get('victim_p95_wait', 0.0),
                    summary.get('victim_metrics', {}).get('victim_p99_wait', 0.0),
                    summary.get('victim_metrics', {}).get('victim_slowdown_ratio', 0.0),
                    summary.get('attacker_metrics', {}).get('attacker_mean_turnaround', 0.0),
                    summary.get('attacker_metrics', {}).get('DPR_A', 0.0),
                    summary.get('attacker_metrics', {}).get('attacker_effective_service', 0.0),
                    summary.get('system_metrics', {}).get('mean_wait', 0.0),
                    summary.get('system_metrics', {}).get('mean_turnaround', 0.0),
                    summary.get('system_metrics', {}).get('throughput', 0.0),
                    summary.get('system_metrics', {}).get('wait_fairness', 0.0),
                    summary.get('system_metrics', {}).get('worst_tenant_degradation', 0.0),
                    summary.get('system_metrics', {}).get('fidelity_proxy_cost', 0.0),
                ])
    return results


def export_tradeoff_summary(output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tradeoff = run_tradeoff(heavy)
    path = output_dir / 'paper_tradeoff_summary.json'
    path.write_text(json.dumps(tradeoff, indent=2), encoding='utf-8')
    return tradeoff


def export_ablation_summary(output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ablation = run_contention_robust_ablation(heavy())
    path = output_dir / 'paper_ablation_summary.json'
    path.write_text(json.dumps(ablation, indent=2), encoding='utf-8')

    csv_path = output_dir / 'paper_ablation_summary.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ablation',
            'victim_mean_wait', 'victim_p99_wait', 'victim_slowdown_ratio',
            'attacker_mean_turnaround', 'attacker_DPR_A', 'attacker_effective_service',
            'system_mean_wait', 'system_mean_turnaround', 'throughput',
            'wait_fairness', 'worst_tenant_degradation', 'fidelity_proxy_cost',
        ])
        for name, summary in ablation.items():
            writer.writerow([
                name,
                summary.get('victim_metrics', {}).get('victim_mean_wait', 0.0),
                summary.get('victim_metrics', {}).get('victim_p99_wait', 0.0),
                summary.get('victim_metrics', {}).get('victim_slowdown_ratio', 0.0),
                summary.get('attacker_metrics', {}).get('attacker_mean_turnaround', 0.0),
                summary.get('attacker_metrics', {}).get('DPR_A', 0.0),
                summary.get('attacker_metrics', {}).get('attacker_effective_service', 0.0),
                summary.get('system_metrics', {}).get('mean_wait', 0.0),
                summary.get('system_metrics', {}).get('mean_turnaround', 0.0),
                summary.get('system_metrics', {}).get('throughput', 0.0),
                summary.get('system_metrics', {}).get('wait_fairness', 0.0),
                summary.get('system_metrics', {}).get('worst_tenant_degradation', 0.0),
                summary.get('system_metrics', {}).get('fidelity_proxy_cost', 0.0),
            ])
    return ablation
