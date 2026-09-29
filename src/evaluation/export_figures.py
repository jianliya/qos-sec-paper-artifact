from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def write_line_svg(path: Path, title: str, x_labels: list[str], series: dict[str, list[float]]) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for name, ys in series.items():
        ax.plot(x_labels, ys, marker='o', linewidth=2, label=name)
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def export_sweep_tradeoff_figures(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    sweeps = data.get('sweeps', {})
    out_dir.mkdir(parents=True, exist_ok=True)
    for dim, runs in sweeps.items():
        x_labels = list(runs.keys())
        if 'availability' in str(summary_path):
            series = {
                'secure_joint_wait': [runs[x]['scenarios']['secure_joint']['victim_avg_wait']['mean'] for x in x_labels if 'secure_joint' in runs[x]['scenarios']],
                'secure_joint_attack_pressure': [runs[x]['scenarios']['secure_joint']['attacker_delay_pressure_ratio']['mean'] for x in x_labels if 'secure_joint' in runs[x]['scenarios']],
                'queue_wait': [runs[x]['scenarios']['queue']['victim_avg_wait']['mean'] for x in x_labels if 'queue' in runs[x]['scenarios']],
            }
            write_line_svg(out_dir / f'availability_tradeoff_{dim}.svg', f'Availability Tradeoff Sweep: {dim}', x_labels, series)
        else:
            series = {
                'linear_leakage': [runs[x]['metrics']['leakage_advantage']['mean'] for x in x_labels],
                'defended_leakage': [runs[x]['metrics']['defended_leakage_advantage']['mean'] for x in x_labels],
                'defense_gain': [runs[x]['metrics']['defense_gain']['mean'] for x in x_labels],
            }
            write_line_svg(out_dir / f'timing_tradeoff_{dim}.svg', f'Timing Tradeoff Sweep: {dim}', x_labels, series)


def export_hardware_paper_figure(summary_path: Path, out_path: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    runs = data.get('run_summaries', [])
    if not runs:
        raise ValueError('No run_summaries found in hardware summary.')

    run_idx = np.array([r.get('run_index', i) for i, r in enumerate(runs)], dtype=float)
    raw_gap = np.array([r.get('raw_class_gap', 0.0) for r in runs], dtype=float)
    def_gap = np.array([r.get('defended_class_gap', 0.0) for r in runs], dtype=float)
    pending = np.array([(r.get('backend_snapshot_before_run') or {}).get('pending_jobs', 0.0) for r in runs], dtype=float)

    raw_acc = np.array([r.get('raw_threshold_accuracy', 0.0) for r in runs], dtype=float)
    def_acc = np.array([r.get('defended_threshold_accuracy', 0.0) for r in runs], dtype=float)
    chance = 0.5

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 8.8), constrained_layout=True)

    ax = axes[0]
    ax.axhline(0.0, color='gray', linewidth=1, linestyle='--', alpha=0.9)
    ax.plot(run_idx, raw_gap, marker='o', linewidth=2, color='#4c78a8', label='Raw class gap')
    ax.plot(run_idx, def_gap, marker='s', linewidth=2, color='#e45756', label='Defended class gap')
    for x, y0, y1 in zip(run_idx, raw_gap, def_gap):
        ax.vlines(x, min(y0, y1), max(y0, y1), color='0.75', linewidth=1.2, alpha=0.8)
    ax.set_title('Repeated hardware runs: per-run class-gap variability')
    ax.set_xlabel('Run index')
    ax.set_ylabel('Class gap (classB - classA)')
    ax.set_xticks(run_idx)
    ax.legend(frameon=False, loc='best')

    ax2 = ax.twinx()
    ax2.bar(run_idx, pending, alpha=0.15, color='#54a24b', width=0.5, label='Pending jobs')
    ax2.set_ylabel('Pending jobs before run')
    ax2.set_ylim(bottom=0)

    axb = axes[1]
    x_raw, x_def = 0.0, 1.0
    rng = np.linspace(-0.045, 0.045, len(run_idx)) if len(run_idx) > 1 else np.array([0.0])
    for j, (ra, da) in enumerate(zip(raw_acc, def_acc)):
        xr = x_raw + rng[j]
        xd = x_def + rng[j]
        axb.plot([xr, xd], [ra, da], color='0.75', linewidth=1.1, alpha=0.9, zorder=1)
        axb.scatter(xr, ra, color='#4c78a8', s=42, zorder=2)
        axb.scatter(xd, da, color='#e45756', s=42, zorder=2)

    raw_mean = float(np.mean(raw_acc))
    def_mean = float(np.mean(def_acc))
    raw_sd = float(np.std(raw_acc, ddof=1)) if len(raw_acc) > 1 else 0.0
    def_sd = float(np.std(def_acc, ddof=1)) if len(def_acc) > 1 else 0.0
    axb.errorbar([x_raw, x_def], [raw_mean, def_mean], yerr=[raw_sd, def_sd], fmt='D', color='black', ecolor='black', elinewidth=1.2, capsize=4, markersize=6, label=r'Mean $\pm$ SD', zorder=3)
    axb.axhline(chance, color='gray', linestyle='--', linewidth=1.2, alpha=0.9, label='Chance = 0.5')
    axb.set_xlim(-0.35, 1.35)
    axb.set_ylim(0.35, 0.85)
    axb.set_xticks([x_raw, x_def])
    axb.set_xticklabels(['Raw', 'Defended'])
    axb.set_ylabel('Threshold accuracy')
    axb.set_title('Repeated paired runs: threshold accuracy with per-run dots')
    axb.legend(frameon=False, loc='best')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def export_appendix_bundle(out_dir: Path, sources: dict[str, Path]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    appendix = []
    for name, path in sources.items():
        appendix.append(f'{name}: {path}')
    (out_dir / 'appendix_index.txt').write_text('\n'.join(appendix) + '\n', encoding='utf-8')


def export_timing_quantum_ablation(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8')).get('ablations', {})
    if not data:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = list(data.keys())
    leakage_series = {
        'raw_leakage': [data[label]['metrics']['leakage_advantage']['mean'] for label in labels],
        'defended_leakage': [data[label]['metrics']['defended_leakage_advantage']['mean'] for label in labels],
    }
    write_line_svg(out_dir / 'timing_quantum_ablation_leakage.svg', 'Timing Quantum Ablation: Leakage Signal', labels, leakage_series)
    gap_series = {
        'class_gap': [data[label]['metrics']['class_gap']['mean'] for label in labels],
        'classB_minus_noVictim': [data[label]['metrics']['classB_minus_noVictim']['mean'] for label in labels],
        'highIsolation_delta': [data[label]['metrics']['highIsolation_delta_from_classA']['mean'] for label in labels],
    }
    write_line_svg(out_dir / 'timing_quantum_ablation_gap.svg', 'Timing Quantum Ablation: Signal Structure', labels, gap_series)


def export_timing_paired_contrast_focus(summary_path: Path, out_dir: Path, contrast_name: str) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8')).get('contrasts', {})
    contrast = data.get(contrast_name)
    if not contrast:
        return
    runs = contrast.get('runs', [])
    if not runs:
        return

    seeds = [str(run['seed']) for run in runs]
    delta_leak = np.array([run['delta_leakage_advantage'] for run in runs], dtype=float)
    delta_gain = np.array([run['delta_defense_gain'] for run in runs], dtype=float)
    positive_ratio = float(contrast.get('positive_delta_ratio', 0.0))
    mean_delta = float(np.mean(delta_leak))

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 8.2), constrained_layout=True)

    ax = axes[0]
    xs = np.arange(len(seeds))
    colors = ['#54a24b' if y > 0 else '#e45756' if y < 0 else '#9d9d9d' for y in delta_leak]
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1.1, alpha=0.9)
    ax.scatter(xs, delta_leak, s=56, color=colors, zorder=3)
    ax.plot(xs, delta_leak, color='0.75', linewidth=1.0, alpha=0.9, zorder=2)
    ax.axhline(mean_delta, color='#4c78a8', linestyle='-', linewidth=1.4, alpha=0.9, label=f'Mean={mean_delta:.4f}')
    ax.set_title('Paired contrast: co-execution sensitivity contribution')
    ax.set_ylabel('Delta leakage advantage')
    ax.set_xticks(xs)
    ax.set_xticklabels(seeds, rotation=0)
    ax.legend(frameon=False, loc='best')
    ax.text(
        0.98,
        0.06,
        f'positive_delta_ratio = {positive_ratio:.4f}',
        transform=ax.transAxes,
        ha='right',
        va='bottom',
        fontsize=9,
        bbox={'facecolor': 'white', 'alpha': 0.85, 'edgecolor': '0.8'},
    )

    ax2 = axes[1]
    colors2 = ['#54a24b' if y > 0 else '#e45756' if y < 0 else '#9d9d9d' for y in delta_gain]
    ax2.axhline(0.0, color='gray', linestyle='--', linewidth=1.1, alpha=0.9)
    ax2.scatter(xs, delta_gain, s=56, color=colors2, zorder=3)
    ax2.plot(xs, delta_gain, color='0.75', linewidth=1.0, alpha=0.9, zorder=2)
    ax2.set_ylabel('Delta defense gain')
    ax2.set_xlabel('Seed')
    ax2.set_xticks(xs)
    ax2.set_xticklabels(seeds, rotation=0)
    ax2.set_title('Seed-level paired deltas under matched workloads/backends')

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = contrast_name.replace('main_vs_', 'timing_paired_')
    fig.savefig(out_dir / f'{stem}_focus.svg')
    plt.close(fig)


def export_timing_noise_backend_choice_relation(summary_path: Path, out_path: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    profiles = data.get('profiles', {})
    if not profiles:
        return

    ordered_names = ['uniform_noise', 'moderate_heterogeneity', 'high_drift']
    names = [name for name in ordered_names if name in profiles]
    if not names:
        names = list(profiles.keys())

    xs = np.array([profiles[name]['metrics']['backend_choice_entropy']['mean'] for name in names], dtype=float)
    ys = np.array([profiles[name]['metrics']['backend_choice_leakage_advantage']['mean'] for name in names], dtype=float)
    waits = np.array([profiles[name]['metrics']['victim_mean_wait']['mean'] for name in names], dtype=float)
    fshift = np.array([profiles[name]['metrics']['victim_fidelity_proxy_shift']['mean'] for name in names], dtype=float)

    label_map = {
        'uniform_noise': 'Uniform',
        'moderate_heterogeneity': 'Moderate',
        'high_drift': 'High drift',
    }
    color_map = {
        'uniform_noise': '#4c78a8',
        'moderate_heterogeneity': '#f58518',
        'high_drift': '#e45756',
    }

    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.grid(alpha=0.22)

    for idx, name in enumerate(names):
        color = color_map.get(name, '#4c78a8')
        size = 140 + 2200 * max(0.0, ys[idx])
        ax.scatter(xs[idx], ys[idx], s=size, color=color, alpha=0.9, edgecolors='white', linewidth=1.1, zorder=3)
        ax.annotate(
            f"{label_map.get(name, name)}\nwait={waits[idx]:.3f}, ΔF={fshift[idx]:.4f}",
            (xs[idx], ys[idx]),
            xytext=(8, 8 if idx != len(names) - 1 else -28),
            textcoords='offset points',
            fontsize=9,
            bbox={'facecolor': 'white', 'alpha': 0.82, 'edgecolor': '0.85', 'pad': 2.5},
        )

    if len(xs) >= 2:
        order = np.argsort(xs)
        ax.plot(xs[order], ys[order], color='0.6', linewidth=1.1, alpha=0.85, zorder=2)

    ax.set_xlabel('Backend-choice entropy')
    ax.set_ylabel('Backend-choice leakage advantage')
    ax.set_title('Noise Heterogeneity and Backend-Choice Observability')

    xpad = max(0.015, 0.12 * (float(xs.max()) - float(xs.min()) if len(xs) > 1 else 0.1))
    ypad = max(0.01, 0.18 * (float(ys.max()) - float(ys.min()) if len(ys) > 1 else 0.05))
    ax.set_xlim(float(xs.min()) - xpad, float(xs.max()) + xpad)
    ax.set_ylim(max(0.0, float(ys.min()) - ypad), float(ys.max()) + ypad)

    ax.text(
        0.98,
        0.04,
        'Bubble size scales with backend-choice leakage.',
        transform=ax.transAxes,
        ha='right',
        va='bottom',
        fontsize=8.5,
        color='0.35',
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
