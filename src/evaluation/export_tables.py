from __future__ import annotations

import csv
import json
from pathlib import Path


RESULT_TABLE_NOTES = {
    'availability_scheduler_comparison': 'Scheduler comparison under adversarial pressure with paired per-seed workloads/backends; interpret as delay-based service degradation evidence rather than baseline/attack/defense blocking evidence.',
    'timing_joint_defense_main': 'Main timing result family; raw and defended settings correspond to a paired joint defended comparison on the same per-seed workloads/backends, not a scheduler-only ablation.',
    'availability_scheduler_ablation': 'Auxiliary availability ablation family; queue and variant runs are paired on the same per-seed workloads/backends and should be used for tradeoff unpacking, not as the main paper result.',
    'timing_observability_ablation': 'Auxiliary timing ablation family over defended variants / observability-shaping choices.',
    'timing_defense_stability': 'Auxiliary timing stability family summarizing multi-seed robustness of the defended configuration.',
    'timing_quantum_attribution': 'Quantum-specific attribution ablation for timing leakage. Use this as the main supporting evidence that the timing signal is not merely a classical queue artifact.',
    'timing_paired_contrast': 'Paired timing attribution contrasts on identical per-seed workloads/backends with only one factor flipped. Use this as the strongest attribution-strengthening evidence line.',
    'timing_compile_awareness': 'Lightweight compile-aware timing experiment. Interpret it as engineering-chain support that transpilation outputs can reshape scheduler-visible timing and backend-choice observability, not as the primary paper result.',
    'timing_compile_configuration_sweep': 'Second-layer compile sweep over optimization level, transpiler seed, and a minimal layout/routing 2x2 subset. Use it to test whether first-layer compile-control conclusions survive basic compilation-configuration changes before expanding to larger compilation matrices.',
    'timing_noise_heterogeneity': 'Lightweight noise-heterogeneity ablation. Use it to interpret whether backend quality variation amplifies observability, destabilizes it, or mainly shifts victim-side quality under scheduling pressure.',
    'hardware_timing_summary': 'Repeated limited hardware timing validation summary. Use as the main hardware evidence line and interpret it as feasibility-oriented support rather than stable production-grade proof.',
    'hardware_timing_runs': 'Per-run hardware timing summary. Use in appendix or diagnostics to unpack cross-run variability and backend-state context.',
}


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_md(path: Path, headers: list[str], rows: list[list[object]], note: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if note:
        lines.extend([
            f'<!-- semantics: {note} -->',
            '',
        ])
    lines.extend([
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ])
    for row in rows:
        lines.append('| ' + ' | '.join(str(x) for x in row) + ' |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def export_availability_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['scenarios']
    headers = ['scheduler', 'victim_avg_wait', 'victim_p95_wait', 'attacker_avg_wait', 'attacker_delay_pressure_ratio', 'attacker_effective_service', 'avg_utilization', 'victim_degradation_vs_queue']
    rows = []
    for name, metrics in data.items():
        rows.append([
            name,
            metrics['victim_avg_wait']['mean'],
            metrics['victim_p95_wait']['mean'],
            metrics['attacker_avg_wait']['mean'],
            metrics['attacker_delay_pressure_ratio']['mean'],
            metrics['attacker_effective_service']['mean'],
            metrics['avg_utilization']['mean'],
            metrics['victim_degradation_vs_queue']['mean'],
        ])
    note = RESULT_TABLE_NOTES['availability_scheduler_comparison']
    _write_csv(out_dir / 'availability_scheduler_comparison.csv', headers, rows)
    _write_md(out_dir / 'availability_scheduler_comparison.md', headers, rows, note)
    _write_csv(out_dir / 'availability_main.csv', headers, rows)
    _write_md(out_dir / 'availability_main.md', headers, rows, note)


def export_timing_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['metrics']
    headers = ['metric', 'mean', 'ci95']
    keys = ['accuracy', 'leakage_advantage', 'threshold_accuracy', 'threshold_leakage_advantage', 'defended_accuracy', 'defended_leakage_advantage', 'defended_threshold_accuracy', 'defended_threshold_leakage_advantage', 'defense_gain']
    rows = [[k, data[k]['mean'], data[k]['ci95']] for k in keys]
    note = RESULT_TABLE_NOTES['timing_joint_defense_main']
    _write_csv(out_dir / 'timing_joint_defense_main.csv', headers, rows)
    _write_md(out_dir / 'timing_joint_defense_main.md', headers, rows, note)
    _write_csv(out_dir / 'timing_main.csv', headers, rows)
    _write_md(out_dir / 'timing_main.md', headers, rows, note)


def export_ablation_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['ablations']
    headers = ['variant', 'victim_avg_wait', 'attacker_avg_wait', 'attacker_delay_pressure_ratio', 'attacker_effective_service', 'victim_degradation_vs_queue']
    rows = [[name, metrics['victim_avg_wait']['mean'], metrics['attacker_avg_wait']['mean'], metrics['attacker_delay_pressure_ratio']['mean'], metrics['attacker_effective_service']['mean'], metrics['victim_degradation_vs_queue']['mean']] for name, metrics in data.items()]
    note = RESULT_TABLE_NOTES['availability_scheduler_ablation']
    _write_csv(out_dir / 'availability_scheduler_ablation.csv', headers, rows)
    _write_md(out_dir / 'availability_scheduler_ablation.md', headers, rows, note)
    _write_csv(out_dir / 'availability_ablation.csv', headers, rows)
    _write_md(out_dir / 'availability_ablation.md', headers, rows, note)


def export_timing_ablation_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['ablations']
    headers = ['variant', 'leakage_advantage', 'defended_leakage_advantage', 'defense_gain']
    rows = [[name, metrics['leakage_advantage']['mean'], metrics['defended_leakage_advantage']['mean'], metrics['defense_gain']['mean']] for name, metrics in data.items()]
    note = RESULT_TABLE_NOTES['timing_observability_ablation']
    _write_csv(out_dir / 'timing_observability_ablation.csv', headers, rows)
    _write_md(out_dir / 'timing_observability_ablation.md', headers, rows, note)
    _write_csv(out_dir / 'timing_ablation.csv', headers, rows)
    _write_md(out_dir / 'timing_ablation.md', headers, rows, note)


def export_timing_stability_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    headers = ['num_seeds', 'positive_gain_count', 'positive_gain_ratio', 'mean_defense_gain', 'std_defense_gain', 'min_defense_gain', 'max_defense_gain']
    rows = [[data[h] for h in headers]]
    note = RESULT_TABLE_NOTES['timing_defense_stability']
    _write_csv(out_dir / 'timing_defense_stability.csv', headers, rows)
    _write_md(out_dir / 'timing_defense_stability.md', headers, rows, note)
    _write_csv(out_dir / 'timing_stability.csv', headers, rows)
    _write_md(out_dir / 'timing_stability.md', headers, rows, note)


def export_timing_quantum_ablation_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['ablations']
    headers = [
        'ablation',
        'accuracy',
        'leakage_advantage',
        'defended_leakage_advantage',
        'defense_gain',
        'class_gap',
        'classB_minus_noVictim',
        'highIsolation_delta_from_classA',
    ]
    rows = []
    for name, obj in data.items():
        metrics = obj['metrics']
        rows.append([
            name,
            metrics['accuracy']['mean'],
            metrics['leakage_advantage']['mean'],
            metrics['defended_leakage_advantage']['mean'],
            metrics['defense_gain']['mean'],
            metrics['class_gap']['mean'],
            metrics['classB_minus_noVictim']['mean'],
            metrics['highIsolation_delta_from_classA']['mean'],
        ])
    note = RESULT_TABLE_NOTES['timing_quantum_attribution']
    _write_csv(out_dir / 'timing_quantum_ablation.csv', headers, rows)
    _write_md(out_dir / 'timing_quantum_ablation.md', headers, rows, note)


def export_timing_paired_contrast_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['contrasts']
    headers = [
        'contrast',
        'reference',
        'compare',
        'delta_leakage_advantage',
        'delta_leakage_ci95',
        'delta_threshold_leakage_advantage',
        'delta_threshold_leakage_ci95',
        'delta_defense_gain',
        'delta_defense_gain_ci95',
        'delta_class_gap',
        'delta_class_gap_ci95',
        'positive_delta_ratio',
    ]
    rows = []
    for name, obj in data.items():
        metrics = obj['metrics']
        rows.append([
            name,
            obj['reference'],
            obj['compare'],
            metrics['delta_leakage_advantage']['mean'],
            metrics['delta_leakage_advantage']['ci95'],
            metrics['delta_threshold_leakage_advantage']['mean'],
            metrics['delta_threshold_leakage_advantage']['ci95'],
            metrics['delta_defense_gain']['mean'],
            metrics['delta_defense_gain']['ci95'],
            metrics['delta_class_gap']['mean'],
            metrics['delta_class_gap']['ci95'],
            obj['positive_delta_ratio'],
        ])
    note = RESULT_TABLE_NOTES['timing_paired_contrast']
    _write_csv(out_dir / 'timing_paired_contrast.csv', headers, rows)
    _write_md(out_dir / 'timing_paired_contrast.md', headers, rows, note)


def export_timing_compile_awareness_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    profiles = data.get('profiles', {})
    headers = [
        'profile',
        'feature_mode',
        'leakage_advantage',
        'backend_choice_leakage_advantage',
        'defended_leakage_advantage',
        'defense_gain',
        'class_gap',
    ]
    rows = []
    for name, obj in profiles.items():
        metrics = obj['metrics']
        rows.append([
            name,
            obj.get('profile', {}).get('feature_mode', 'compile_visible'),
            metrics['leakage_advantage']['mean'],
            metrics['backend_choice_leakage_advantage']['mean'],
            metrics['defended_leakage_advantage']['mean'],
            metrics['defense_gain']['mean'],
            metrics['class_gap']['mean'],
        ])
    note = RESULT_TABLE_NOTES['timing_compile_awareness']
    _write_csv(out_dir / 'timing_compile_awareness.csv', headers, rows)
    _write_md(out_dir / 'timing_compile_awareness.md', headers, rows, note)

    catalog_headers = [
        'family',
        'backend_id',
        'backend_qubits',
        'compiled_depth',
        'cx_count',
        'swap_count',
        'layout_span',
        'expected_fidelity',
        'backend_suitability',
        'topology',
    ]
    catalog_rows = [
        [row[h] for h in catalog_headers]
        for row in data.get('compile_catalog', [])
    ]
    _write_csv(out_dir / 'timing_compile_catalog.csv', catalog_headers, catalog_rows)
    _write_md(out_dir / 'timing_compile_catalog.md', catalog_headers, catalog_rows, note)

    contrast_headers = [
        'contrast',
        'reference',
        'compare',
        'delta_leakage_advantage',
        'delta_leakage_ci95',
        'delta_backend_choice_leakage_advantage',
        'delta_backend_choice_leakage_ci95',
        'delta_defense_gain',
        'delta_defense_gain_ci95',
        'positive_delta_ratio',
    ]
    contrast_rows = []
    for name, obj in data.get('contrasts', {}).items():
        metrics = obj['metrics']
        contrast_rows.append([
            name,
            obj['reference'],
            obj['compare'],
            metrics['delta_leakage_advantage']['mean'],
            metrics['delta_leakage_advantage']['ci95'],
            metrics['delta_backend_choice_leakage_advantage']['mean'],
            metrics['delta_backend_choice_leakage_advantage']['ci95'],
            metrics['delta_defense_gain']['mean'],
            metrics['delta_defense_gain']['ci95'],
            obj['positive_delta_ratio'],
        ])
    _write_csv(out_dir / 'timing_compile_awareness_contrasts.csv', contrast_headers, contrast_rows)
    _write_md(out_dir / 'timing_compile_awareness_contrasts.md', contrast_headers, contrast_rows, note)


def export_timing_compile_configuration_sweep_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    note = RESULT_TABLE_NOTES['timing_compile_configuration_sweep']

    profile_headers = [
        'optimization_level',
        'transpiler_seed',
        'layout_method',
        'routing_method',
        'profile',
        'feature_mode',
        'leakage_advantage',
        'backend_choice_leakage_advantage',
        'defense_gain',
    ]
    profile_rows = []
    for opt_level, seed_runs in data.get('runs', {}).items():
        for transpiler_seed, obj in seed_runs.items():
            # backward compatibility: older files stop at opt -> seed -> record
            if 'profiles' in obj:
                layout_runs = {'default': {'default': obj}}
            else:
                layout_runs = obj
            for layout_method, routing_runs in layout_runs.items():
                for routing_method, run_obj in routing_runs.items():
                    for profile_name, profile_obj in run_obj.get('profiles', {}).items():
                        profile_rows.append([
                            opt_level,
                            transpiler_seed,
                            layout_method,
                            routing_method,
                            profile_name,
                            profile_obj.get('feature_mode', 'compile_visible'),
                            profile_obj.get('leakage_advantage', 0.0),
                            profile_obj.get('backend_choice_leakage_advantage', 0.0),
                            profile_obj.get('defense_gain', 0.0),
                        ])
    _write_csv(out_dir / 'timing_compile_configuration_sweep_profiles.csv', profile_headers, profile_rows)
    _write_md(out_dir / 'timing_compile_configuration_sweep_profiles.md', profile_headers, profile_rows, note)

    contrast_headers = [
        'optimization_level',
        'transpiler_seed',
        'layout_method',
        'routing_method',
        'contrast',
        'reference',
        'compare',
        'delta_leakage_advantage',
        'delta_leakage_ci95',
        'delta_backend_choice_leakage_advantage',
        'delta_backend_choice_leakage_ci95',
        'positive_delta_ratio',
    ]
    contrast_rows = []
    for opt_level, seed_runs in data.get('runs', {}).items():
        for transpiler_seed, obj in seed_runs.items():
            if 'contrasts' in obj:
                layout_runs = {'default': {'default': obj}}
            else:
                layout_runs = obj
            for layout_method, routing_runs in layout_runs.items():
                for routing_method, run_obj in routing_runs.items():
                    for contrast_name, contrast_obj in run_obj.get('contrasts', {}).items():
                        contrast_rows.append([
                            opt_level,
                            transpiler_seed,
                            layout_method,
                            routing_method,
                            contrast_name,
                            contrast_obj.get('reference', ''),
                            contrast_obj.get('compare', ''),
                            contrast_obj.get('delta_leakage_advantage', 0.0),
                            contrast_obj.get('delta_leakage_ci95', 0.0),
                            contrast_obj.get('delta_backend_choice_leakage_advantage', 0.0),
                            contrast_obj.get('delta_backend_choice_leakage_ci95', 0.0),
                            contrast_obj.get('positive_delta_ratio', 0.0),
                        ])
    _write_csv(out_dir / 'timing_compile_configuration_sweep_contrasts.csv', contrast_headers, contrast_rows)
    _write_md(out_dir / 'timing_compile_configuration_sweep_contrasts.md', contrast_headers, contrast_rows, note)


def export_timing_noise_heterogeneity_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    profiles = data.get('profiles', {})
    headers = [
        'profile',
        'leakage_advantage',
        'backend_choice_entropy',
        'score_margin_variance',
        'victim_mean_wait',
        'victim_fidelity_proxy_shift',
        'backend_choice_leakage_advantage',
    ]
    rows = []
    for name, obj in profiles.items():
        metrics = obj['metrics']
        rows.append([
            name,
            metrics['leakage_advantage']['mean'],
            metrics['backend_choice_entropy']['mean'],
            metrics['score_margin_variance']['mean'],
            metrics['victim_mean_wait']['mean'],
            metrics['victim_fidelity_proxy_shift']['mean'],
            metrics['backend_choice_leakage_advantage']['mean'],
        ])
    note = RESULT_TABLE_NOTES['timing_noise_heterogeneity']
    _write_csv(out_dir / 'timing_noise_heterogeneity.csv', headers, rows)
    _write_md(out_dir / 'timing_noise_heterogeneity.md', headers, rows, note)

    contrast_headers = [
        'contrast',
        'reference',
        'compare',
        'delta_adv_noise',
        'delta_adv_noise_ci95',
        'delta_backend_entropy',
        'delta_backend_entropy_ci95',
        'delta_score_margin_variance',
        'delta_score_margin_variance_ci95',
        'delta_victim_wait',
        'delta_victim_wait_ci95',
        'delta_fproxy_shift',
        'delta_fproxy_shift_ci95',
    ]
    contrast_rows = []
    for name, obj in data.get('contrasts', {}).items():
        metrics = obj['metrics']
        contrast_rows.append([
            name,
            obj['reference'],
            obj['compare'],
            metrics['delta_adv_noise']['mean'],
            metrics['delta_adv_noise']['ci95'],
            metrics['delta_backend_entropy']['mean'],
            metrics['delta_backend_entropy']['ci95'],
            metrics['delta_score_margin_variance']['mean'],
            metrics['delta_score_margin_variance']['ci95'],
            metrics['delta_victim_wait']['mean'],
            metrics['delta_victim_wait']['ci95'],
            metrics['delta_fproxy_shift']['mean'],
            metrics['delta_fproxy_shift']['ci95'],
        ])
    _write_csv(out_dir / 'timing_noise_heterogeneity_contrast.csv', contrast_headers, contrast_rows)
    _write_md(out_dir / 'timing_noise_heterogeneity_contrast.md', contrast_headers, contrast_rows, note)


def export_hardware_timing_tables(summary_path: Path, out_dir: Path) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))
    agg = data.get('aggregate', {})
    raw = agg.get('raw', {})
    coarse = agg.get('coarse_bucket', {})
    grouped = agg.get('grouped_release', {})
    summary_headers = ['metric', 'raw', 'coarse_bucket', 'grouped_release']
    summary_rows = [
        ['mean_threshold_accuracy', raw.get('mean_threshold_accuracy', 0.0), coarse.get('mean_threshold_accuracy', 0.0), grouped.get('mean_threshold_accuracy', 0.0)],
        ['mean_leakage_advantage', raw.get('mean_leakage_advantage', 0.0), coarse.get('mean_leakage_advantage', 0.0), grouped.get('mean_leakage_advantage', 0.0)],
        ['mean_class_gap', raw.get('mean_class_gap', 0.0), coarse.get('mean_class_gap', 0.0), grouped.get('mean_class_gap', 0.0)],
        ['mean_effect_size', raw.get('mean_effect_size', 0.0), coarse.get('mean_effect_size', 0.0), grouped.get('mean_effect_size', 0.0)],
        ['positive_gap_ratio', raw.get('positive_gap_ratio', 0.0), coarse.get('positive_gap_ratio', 0.0), grouped.get('positive_gap_ratio', 0.0)],
    ]
    summary_note = RESULT_TABLE_NOTES['hardware_timing_summary']
    _write_csv(out_dir / 'hardware_timing_summary.csv', summary_headers, summary_rows)
    _write_md(out_dir / 'hardware_timing_summary.md', summary_headers, summary_rows, summary_note)

    run_headers = [
        'run_index', 'date_window', 'raw_threshold_accuracy', 'coarse_threshold_accuracy', 'grouped_threshold_accuracy',
        'raw_class_gap', 'coarse_class_gap', 'grouped_class_gap', 'pending_jobs', 'operational', 'snapshot_ts'
    ]
    run_rows = []
    for run in data.get('run_summaries', []):
        snap = run.get('backend_snapshot_before_run') or {}
        raw_metrics = run.get('raw_metrics', {})
        coarse_metrics = run.get('coarse_bucket_metrics', {})
        grouped_metrics = run.get('grouped_release_metrics', {})
        run_rows.append([
            run.get('run_index', 0),
            run.get('date_window', ''),
            raw_metrics.get('threshold_accuracy', 0.0),
            coarse_metrics.get('threshold_accuracy', 0.0),
            grouped_metrics.get('threshold_accuracy', 0.0),
            raw_metrics.get('class_gap', 0.0),
            coarse_metrics.get('class_gap', 0.0),
            grouped_metrics.get('class_gap', 0.0),
            snap.get('pending_jobs', 0.0),
            snap.get('operational', True),
            snap.get('snapshot_ts', 0.0),
        ])
    runs_note = RESULT_TABLE_NOTES['hardware_timing_runs']
    _write_csv(out_dir / 'hardware_timing_runs.csv', run_headers, run_rows)
    _write_md(out_dir / 'hardware_timing_runs.md', run_headers, run_rows, runs_note)


def export_sweep_tables(summary_path: Path, out_dir: Path, key_metric: str, value_metric: str, name: str) -> None:
    data = json.loads(summary_path.read_text(encoding='utf-8'))['runs']
    rows = []
    headers = ['dimension', 'value', 'series', value_metric]
    for dim, dim_runs in data.items():
        for value, obj in dim_runs.items():
            target = obj['scenarios'] if 'scenarios' in obj else obj['metrics']
            if 'scenarios' in obj:
                for series, metrics in target.items():
                    rows.append([dim, value, series, metrics[value_metric]['mean']])
            else:
                rows.append([dim, value, key_metric, target[value_metric]['mean']])
    note = 'Sensitivity / tradeoff evidence line; use as auxiliary support rather than as the primary paper result.'
    _write_csv(out_dir / f'{name}.csv', headers, rows)
    _write_md(out_dir / f'{name}.md', headers, rows, note)
