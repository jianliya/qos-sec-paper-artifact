from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
AVAIL = ROOT / 'results' / 'availability' / 'summary_multiseed.json'
TIMING = ROOT / 'results' / 'timing' / 'summary_multiseed.json'
OUT = ROOT / 'plots' / 'paper'


def bar_pdf(path: Path, title: str, labels: list[str], values: list[float], ylabel: str, color: str = '#4c78a8', errors: list[float] | None = None, ylim: tuple[float, float] | None = None, hlines: list[tuple[float, str, str]] | None = None):
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    bars = ax.bar(labels, values, color=color, yerr=errors, capsize=4, ecolor='black', error_kw={'elinewidth': 1.1} if errors else None)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)
    if hlines:
        for y, style, label in hlines:
            ax.axhline(y, linestyle=style, linewidth=1.2, color='gray', alpha=0.9, label=label)
        ax.legend(frameon=False, loc='best')
    ymax = max((v + (e if errors else 0.0)) for v, e in zip(values, errors or [0.0] * len(values))) if values else 1.0
    for b, v, e in zip(bars, values, errors or [0.0] * len(values)):
        ax.text(b.get_x() + b.get_width() / 2, v + e + max(0.01 * max(ymax, 1.0), 0.003), f'{v:.3f}', ha='center', va='bottom', fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def grouped_bar_pdf(path: Path, title: str, labels: list[str], series: dict[str, list[float]], ylabel: str, errors: dict[str, list[float]] | None = None, baseline: float | None = None, baseline_label: str | None = None, ylim: tuple[float, float] | None = None):
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    x = list(range(len(labels)))
    width = 0.35 if len(series) == 2 else 0.22
    colors = ['#4c78a8', '#e45756', '#54a24b']
    offsets = []
    n = len(series)
    for idx in range(n):
        offsets.append((idx - (n - 1) / 2) * width)
    if baseline is not None:
        ax.axhline(baseline, color='gray', linestyle='--', linewidth=1.2, label=baseline_label or f'Baseline={baseline:.2f}')
    ymax = 0.0
    for idx, (name, values) in enumerate(series.items()):
        errs = (errors or {}).get(name)
        bars = ax.bar([i + offsets[idx] for i in x], values, width=width, label=name, color=colors[idx % len(colors)], yerr=errs, capsize=4, ecolor='black', error_kw={'elinewidth': 1.0} if errs else None)
        series_top = max((v + (errs[i] if errs else 0.0) for i, v in enumerate(values)), default=ymax)
        ymax = max(ymax, series_top)
        for i, (b, v) in enumerate(zip(bars, values)):
            err = errs[i] if errs else 0.0
            ax.text(b.get_x() + b.get_width() / 2, v + err + max(0.01 * max(ymax, 1.0), 0.003), f'{v:.3f}', ha='center', va='bottom', fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    avail = json.loads(AVAIL.read_text(encoding='utf-8'))['scenarios']
    timing = json.loads(TIMING.read_text(encoding='utf-8'))['metrics']

    avail_labels = ['Queue', 'Balanced', 'Quota', 'Isolation', 'SecureJoint']
    avail_keys = ['queue', 'balanced', 'quota', 'isolation', 'secure_joint']
    bar_pdf(
        OUT / 'availability_victim_wait.pdf',
        'Victim Average Wait under Adversarial Pressure',
        avail_labels,
        [avail[k]['victim_avg_wait']['mean'] for k in avail_keys],
        'Average wait',
        color='#4c78a8',
        errors=[avail[k]['victim_avg_wait']['ci95'] for k in avail_keys],
    )
    bar_pdf(
        OUT / 'availability_attacker_pressure.pdf',
        'Attacker Delay Pressure by Scheduler Policy',
        avail_labels,
        [avail[k]['attacker_delay_pressure_ratio']['mean'] for k in avail_keys],
        'Pressure ratio',
        color='#54a24b',
        errors=[avail[k]['attacker_delay_pressure_ratio']['ci95'] for k in avail_keys],
        ylim=(0.0, 1.0),
    )

    bar_pdf(
        OUT / 'timing_mean_waits.pdf',
        'Probe Mean Wait by Victim Setting',
        ['ClassA', 'ClassB', 'HighIso', 'NoVictim'],
        [
            timing['classA_mean_wait']['mean'],
            timing['classB_mean_wait']['mean'],
            timing['highIsolation_mean_wait']['mean'],
            timing['noVictim_mean_wait']['mean'],
        ],
        'Probe wait',
        color='#4c78a8',
        errors=[
            timing['classA_mean_wait']['ci95'],
            timing['classB_mean_wait']['ci95'],
            timing['highIsolation_mean_wait']['ci95'],
            timing['noVictim_mean_wait']['ci95'],
        ],
    )
    grouped_bar_pdf(
        OUT / 'timing_signal_metrics.pdf',
        'Timing Inference Metrics: Raw vs Defended',
        ['Accuracy', 'LeakAdv', 'ThresholdAcc', 'DefenseGain'],
        {
            'Raw': [
                timing['accuracy']['mean'],
                timing['leakage_advantage']['mean'],
                timing['threshold_accuracy']['mean'],
                timing['defense_gain']['mean'],
            ],
            'Defended': [
                timing['defended_accuracy']['mean'],
                timing['defended_leakage_advantage']['mean'],
                timing['defended_threshold_accuracy']['mean'],
                0.0,
            ],
        },
        'Value',
        errors={
            'Raw': [
                timing['accuracy']['ci95'],
                timing['leakage_advantage']['ci95'],
                timing['threshold_accuracy']['ci95'],
                timing['defense_gain']['ci95'],
            ],
            'Defended': [
                timing['defended_accuracy']['ci95'],
                timing['defended_leakage_advantage']['ci95'],
                timing['defended_threshold_accuracy']['ci95'],
                0.0,
            ],
        },
        baseline=0.5,
        baseline_label='Chance / prior baseline = 0.5',
        ylim=(-0.1, 0.8),
    )


if __name__ == '__main__':
    main()
