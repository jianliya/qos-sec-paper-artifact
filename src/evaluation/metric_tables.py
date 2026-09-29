from __future__ import annotations

from pathlib import Path
import csv


def export_primary_metric_table(results: dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'scheduler',
            'victim_mean_wait',
            'victim_mean_turnaround',
            'attacker_mean_wait',
            'attacker_mean_turnaround',
            'system_mean_wait',
            'system_mean_turnaround',
            'wait_fairness',
        ])
        for scheduler_name, summary in results.items():
            victim = summary.get('victim_metrics', {})
            attacker = summary.get('attacker_metrics', {})
            system = summary.get('system_metrics', {})
            writer.writerow([
                scheduler_name,
                victim.get('victim_mean_wait', 0.0),
                victim.get('victim_mean_turnaround', 0.0),
                attacker.get('attacker_mean_wait', 0.0),
                attacker.get('attacker_mean_turnaround', 0.0),
                system.get('mean_wait', 0.0),
                system.get('mean_turnaround', 0.0),
                system.get('wait_fairness', 0.0),
            ])
