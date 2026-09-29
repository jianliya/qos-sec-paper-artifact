from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'figures' / 'appendix'


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def availability_ablation():
    data = json.loads((ROOT / 'results' / 'ablations' / 'availability_ablation.json').read_text())['ablations']
    labels = list(data.keys())
    pressure = [data[k]['attacker_delay_pressure_ratio']['mean'] for k in labels]
    wait = [data[k]['victim_avg_wait']['mean'] for k in labels]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, pressure, color='#54a24b')
    ax.set_title('Availability ablation: attacker delay pressure')
    ax.set_ylabel('Pressure ratio')
    ax.tick_params(axis='x', rotation=25)
    _save(fig, OUT / 'availability_ablation_attack_success.pdf')

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, wait, color='#4c78a8')
    ax.set_title('Availability ablation: victim average wait')
    ax.set_ylabel('Victim average wait')
    ax.tick_params(axis='x', rotation=25)
    _save(fig, OUT / 'availability_ablation_wait.pdf')


def availability_tradeoff():
    data = json.loads((ROOT / 'results' / 'availability' / 'summary_multiseed.json').read_text())['scenarios']
    labels = list(data.keys())
    util = [data[k]['avg_utilization']['mean'] for k in labels]
    degr = [data[k]['victim_degradation_vs_queue']['mean'] for k in labels]
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    ax.scatter(util, degr, s=90, color='#e45756')
    for x, y, label in zip(util, degr, labels):
        ax.text(x, y, label, fontsize=9, ha='left', va='bottom')
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Availability tradeoff across scheduler policies')
    ax.set_xlabel('Average utilization')
    ax.set_ylabel('Victim degradation vs. queue')
    _save(fig, OUT / 'availability_tradeoff.pdf')


def availability_sensitivity():
    data = json.loads((ROOT / 'results' / 'sweeps' / 'availability_sweep.json').read_text())['runs']
    for dim, fname in [('attacker_demand', 'availability_tradeoff_attacker_demand.pdf'), ('attacker_jobs', 'availability_tradeoff_attacker_jobs.pdf')]:
        runs = data[dim]
        xvals = list(runs.keys())
        fig, ax = plt.subplots(figsize=(6.6, 4.2))
        for scheduler in ['queue', 'balanced', 'quota', 'isolation', 'secure_joint']:
            y = [runs[x]['scenarios'][scheduler]['victim_degradation_vs_queue']['mean'] for x in xvals]
            ax.plot(xvals, y, marker='o', label=scheduler)
        ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
        ax.set_title(f'Availability sensitivity: {dim.replace("_", " ")}')
        ax.set_xlabel(dim.replace('_', ' '))
        ax.set_ylabel('Victim degradation vs. queue')
        ax.legend(frameon=False, ncol=2, fontsize=8)
        _save(fig, OUT / fname)


def timing_ablation():
    data = json.loads((ROOT / 'results' / 'ablations' / 'timing_ablation.json').read_text())['ablations']
    labels = list(data.keys())
    defended = [data[k]['defended_leakage_advantage']['mean'] for k in labels]
    gain = [data[k]['defense_gain']['mean'] for k in labels]

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, defended, color='#e45756')
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Timing ablation: defended leakage advantage')
    ax.set_ylabel('Defended leakage advantage')
    ax.tick_params(axis='x', rotation=25)
    _save(fig, OUT / 'timing_ablation_defended_leak.pdf')

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, gain, color='#54a24b')
    ax.set_title('Timing ablation: defense gain')
    ax.set_ylabel('Defense gain')
    ax.tick_params(axis='x', rotation=25)
    _save(fig, OUT / 'timing_ablation_gain.pdf')


def timing_stability():
    data = json.loads((ROOT / 'results' / 'stability' / 'timing_stability.json').read_text())
    labels = ['PositiveGainRatio', 'MeanGain', 'MinGain', 'MaxGain']
    vals = [data['positive_gain_ratio'], data['mean_defense_gain'], data['min_defense_gain'], data['max_defense_gain']]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    bars = ax.bar(labels, vals, color=['#54a24b', '#4c78a8', '#f58518', '#e45756'])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v, f'{v:.3f}', ha='center', va='bottom', fontsize=9)
    ax.set_title('Timing stability summary of defended configuration')
    ax.set_ylabel('Value')
    _save(fig, OUT / 'timing_stability_summary.pdf')


def timing_sensitivity():
    data = json.loads((ROOT / 'results' / 'sweeps' / 'timing_sweep.json').read_text())['runs']
    probe_runs = data['probe_jobs']
    xvals = list(probe_runs.keys())
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    raw = [probe_runs[x]['metrics']['leakage_advantage']['mean'] for x in xvals]
    defended = [probe_runs[x]['metrics']['defended_leakage_advantage']['mean'] for x in xvals]
    ax.plot(xvals, raw, marker='o', color='#4c78a8', label='Raw leak. adv.')
    ax.plot(xvals, defended, marker='s', color='#e45756', label='Defended leak. adv.')
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    ax.set_title('Timing sensitivity: probe-job budget')
    ax.set_xlabel('Probe jobs')
    ax.set_ylabel('Leakage advantage')
    ax.legend(frameon=False)
    _save(fig, OUT / 'timing_tradeoff_probe_jobs.pdf')

    obs_runs = data['observability_mode']
    labels = list(obs_runs.keys())
    gain = [obs_runs[x]['metrics']['defense_gain']['mean'] for x in labels]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.bar(labels, gain, color='#54a24b')
    ax.set_title('Timing sensitivity: observability mode')
    ax.set_ylabel('Defense gain')
    ax.tick_params(axis='x', rotation=20)
    _save(fig, OUT / 'timing_tradeoff_observability_mode.pdf')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    availability_ablation()
    availability_tradeoff()
    availability_sensitivity()
    timing_ablation()
    timing_stability()
    timing_sensitivity()


if __name__ == '__main__':
    main()
