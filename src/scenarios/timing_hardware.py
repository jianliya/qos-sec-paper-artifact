from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import mean, pstdev

from hardware.ibm_backend_snapshot import snapshot_backend
from hardware.ibm_circuits import build_victim_circuit
from hardware.ibm_job_runner import run_sampler_job
from hardware.ibm_runtime import IBMRuntimeUnavailable, list_candidate_backends, load_service

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / 'results' / 'hardware'


def _threshold_classifier(class_a: list[dict], class_b: list[dict]) -> dict:
    a = [x.get('observed_wait', 0.0) for x in class_a]
    b = [x.get('observed_wait', 0.0) for x in class_b]
    if not a or not b:
        return {
            'threshold_accuracy': 0.0,
            'threshold_leakage_advantage': 0.0,
            'threshold': 0.0,
            'direction': 'unknown',
            'class_a_mean': 0.0,
            'class_b_mean': 0.0,
        }
    mean_a = mean(a)
    mean_b = mean(b)
    thr = (mean_a + mean_b) / 2.0
    total = len(a) + len(b)
    acc_forward = (sum(int(x < thr) for x in a) + sum(int(x >= thr) for x in b)) / total if total else 0.0
    acc_reverse = (sum(int(x >= thr) for x in a) + sum(int(x < thr) for x in b)) / total if total else 0.0
    if acc_forward >= acc_reverse:
        acc = acc_forward
        direction = 'A_lt_thr_B_ge_thr'
    else:
        acc = acc_reverse
        direction = 'A_ge_thr_B_lt_thr'
    return {
        'threshold_accuracy': round(acc, 4),
        'threshold_leakage_advantage': round(acc - 0.5, 4),
        'threshold': round(thr, 4),
        'direction': direction,
        'class_a_mean': round(mean_a, 4),
        'class_b_mean': round(mean_b, 4),
    }


def _record_to_dict(rec, *, block_id: int, position_in_block: int, date_window: str, task_family: str, block_pattern: str) -> dict:
    return {
        'date_window': date_window,
        'block_id': block_id,
        'position_in_block': position_in_block,
        'block_pattern': block_pattern,
        'task_family': task_family,
        'job_id': rec.job_id,
        'backend_id': rec.backend_id,
        'submit_ts': round(rec.submit_ts, 4),
        'start_ts_proxy': None,
        'end_ts': round(rec.end_ts, 4),
        'elapsed_time': round(rec.latency, 4),
        'latency': round(rec.latency, 4),
        'shots': rec.shots,
        'status': rec.status,
        'num_qubits': rec.num_qubits,
        'depth': rec.depth,
        'size': rec.size,
        'two_qubit_gates': rec.two_qubit_gates,
        'counts': rec.counts,
        'notes': '',
    }


def _extract_waits(entries: list[dict]) -> list[float]:
    return [float(x.get('observed_wait', 0.0)) for x in entries if x.get('observed_wait') is not None]


def _mean_metric(entries: list[dict], field: str) -> float:
    vals = [float(x[field]) for x in entries if x.get(field) is not None]
    return round(mean(vals), 4) if vals else 0.0


def _std_metric(entries: list[dict], field: str) -> float:
    vals = [float(x[field]) for x in entries if x.get(field) is not None]
    return round(pstdev(vals), 4) if len(vals) > 1 else 0.0


def _class_gap(class_a: list[dict], class_b: list[dict]) -> float:
    a = _extract_waits(class_a)
    b = _extract_waits(class_b)
    if not a or not b:
        return 0.0
    return round(mean(b) - mean(a), 4)


def _effect_size(class_a: list[dict], class_b: list[dict]) -> float:
    a = _extract_waits(class_a)
    b = _extract_waits(class_b)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    std_a = pstdev(a)
    std_b = pstdev(b)
    pooled = ((std_a ** 2 + std_b ** 2) / 2.0) ** 0.5
    if pooled <= 1e-9:
        return 0.0
    return round((mean(b) - mean(a)) / pooled, 4)


def _block_patterns(cfg: dict) -> list[str]:
    patterns = cfg.get('block_patterns')
    if isinstance(patterns, list) and patterns:
        return [str(x).upper() for x in patterns]
    default_pattern = str(cfg.get('pair_design', 'ABBA')).upper()
    if default_pattern not in {'ABBA', 'BAAB', 'ABAB'}:
        default_pattern = 'ABBA'
    return [default_pattern]


def _build_schedule(cfg: dict) -> list[dict]:
    block_count = int(cfg.get('paired_blocks', cfg.get('rounds_per_class', cfg.get('victim_jobs', 4))))
    patterns = _block_patterns(cfg)
    schedule: list[dict] = []
    for block_id in range(block_count):
        pattern = patterns[block_id % len(patterns)]
        for position, label in enumerate(pattern):
            schedule.append({
                'block_id': block_id,
                'position_in_block': position,
                'label': 'classA' if label == 'A' else 'classB',
                'task_family': 'HW-A' if label == 'A' else 'HW-B',
                'block_pattern': pattern,
            })
    return schedule


def _backend_name(backend) -> str:
    return str(getattr(backend, 'name', 'unknown_backend'))


def _date_window_labels(cfg: dict, num_runs: int) -> list[str]:
    labels = cfg.get('date_window_labels')
    if isinstance(labels, list) and labels:
        return [str(x) for x in labels]
    return [f'window_{idx + 1}' for idx in range(num_runs)]


def _observe_raw(record: dict, *, decimal_places: int) -> dict:
    return {
        'observed_wait': round(float(record.get('elapsed_time', 0.0)), decimal_places),
        'queue_length': None,
        'backend_id': record.get('backend_id'),
        'observation_mode': 'raw',
    }


def _observe_coarse_bucket(record: dict, *, bucket_size_s: float) -> dict:
    elapsed = float(record.get('elapsed_time', 0.0))
    bucket = round(round(elapsed / bucket_size_s) * bucket_size_s, 4) if bucket_size_s > 0 else round(elapsed, 4)
    return {
        'observed_wait': bucket,
        'queue_length': None,
        'backend_id': record.get('backend_id'),
        'observation_mode': 'coarse_bucket',
        'bucket_size_s': bucket_size_s,
    }


def _observe_grouped_release(entries: list[dict], *, grouping_mode: str) -> list[dict]:
    if not entries:
        return []
    grouped: list[dict] = []
    groups: dict[int, list[dict]] = {}
    for entry in entries:
        groups.setdefault(int(entry['block_id']), []).append(entry)
    for block_id in sorted(groups):
        block_entries = sorted(groups[block_id], key=lambda x: int(x['position_in_block']))
        if grouping_mode == 'block_mean':
            block_value = round(mean(float(x.get('elapsed_time', 0.0)) for x in block_entries), 4)
            for entry in block_entries:
                grouped.append({
                    **entry,
                    'observed_wait': block_value,
                    'queue_length': len(block_entries),
                    'backend_id': 'grouped',
                    'observation_mode': 'grouped_block_mean',
                })
            continue

        by_label: dict[str, list[dict]] = {'HW-A': [], 'HW-B': []}
        for entry in block_entries:
            by_label[str(entry.get('task_family'))].append(entry)
        family_means = {
            family: round(mean(float(x.get('elapsed_time', 0.0)) for x in xs), 4) if xs else 0.0
            for family, xs in by_label.items()
        }
        for entry in block_entries:
            grouped.append({
                **entry,
                'observed_wait': family_means.get(str(entry.get('task_family')), 0.0),
                'queue_length': len(block_entries),
                'backend_id': 'grouped',
                'observation_mode': 'grouped_family_mean',
            })
    return grouped


def _variant_entries(records: list[dict], cfg: dict) -> dict[str, list[dict]]:
    raw_decimal_places = int(cfg.get('raw_decimal_places', 4))
    coarse_bucket_s = float(cfg.get('coarse_bucket_s', 1.0))
    grouped_mode = str(cfg.get('grouped_observation_mode', 'family_mean'))

    raw = []
    coarse = []
    for rec in records:
        raw_obs = _observe_raw(rec, decimal_places=raw_decimal_places)
        raw.append({**rec, **raw_obs})
        coarse_obs = _observe_coarse_bucket(rec, bucket_size_s=coarse_bucket_s)
        coarse.append({**rec, **coarse_obs})

    return {
        'raw': raw,
        'coarse_bucket': coarse,
        'grouped_release': _observe_grouped_release(records, grouping_mode=grouped_mode),
    }


def _collect_variant_metrics(entries: list[dict]) -> dict:
    class_a = [x for x in entries if x.get('task_family') == 'HW-A']
    class_b = [x for x in entries if x.get('task_family') == 'HW-B']
    thr = _threshold_classifier(class_a, class_b)
    waits = _extract_waits(entries)
    gap = _class_gap(class_a, class_b)
    effect = _effect_size(class_a, class_b)
    return {
        'threshold_accuracy': thr['threshold_accuracy'],
        'leakage_advantage': thr['threshold_leakage_advantage'],
        'threshold': thr['threshold'],
        'direction': thr['direction'],
        'classA_mean': thr['class_a_mean'],
        'classB_mean': thr['class_b_mean'],
        'class_gap': gap,
        'effect_size': effect,
        'probe_mean_wait': round(mean(waits), 4) if waits else 0.0,
        'probe_std_wait': round(pstdev(waits), 4) if len(waits) > 1 else 0.0,
        'classA_probe_mean_wait': _mean_metric(class_a, 'observed_wait'),
        'classB_probe_mean_wait': _mean_metric(class_b, 'observed_wait'),
    }


def _block_gap_summary(entries: list[dict]) -> dict:
    if not entries:
        return {
            'per_block_gap': [],
            'mean_gap': 0.0,
            'std_gap': 0.0,
            'positive_gap_ratio': 0.0,
        }
    blocks: dict[int, list[dict]] = {}
    for entry in entries:
        blocks.setdefault(int(entry['block_id']), []).append(entry)
    per_block_gap = []
    for block_id, block_entries in sorted(blocks.items()):
        class_a = [x for x in block_entries if x.get('task_family') == 'HW-A']
        class_b = [x for x in block_entries if x.get('task_family') == 'HW-B']
        gap = _class_gap(class_a, class_b)
        per_block_gap.append({'block_id': block_id, 'gap': gap})
    gaps = [float(x['gap']) for x in per_block_gap]
    return {
        'per_block_gap': per_block_gap,
        'mean_gap': round(mean(gaps), 4) if gaps else 0.0,
        'std_gap': round(pstdev(gaps), 4) if len(gaps) > 1 else 0.0,
        'positive_gap_ratio': round(sum(1 for gap in gaps if gap > 0) / max(len(gaps), 1), 4),
    }


def _analyze_variants(records: list[dict], cfg: dict) -> dict:
    variant_entries = _variant_entries(records, cfg)
    analyses = {}
    for name, entries in variant_entries.items():
        analyses[name] = {
            'metrics': _collect_variant_metrics(entries),
            'block_gap_summary': _block_gap_summary(entries),
        }
    return analyses


def _run_single_study(service, backend, cfg: dict, run_index: int, date_window: str) -> dict:
    del service
    shots = int(cfg.get('shots', 16))
    schedule = _build_schedule(cfg)
    run_start_ts = time.time()
    snapshot_before = snapshot_backend(backend) if cfg.get('record_backend_snapshot_each_run', True) else None

    records = []
    blocks = []
    current_block = None
    for item in schedule:
        block_id = int(item['block_id'])
        if current_block != block_id:
            current_block = block_id
            block_snapshot_before = snapshot_backend(backend) if cfg.get('record_backend_snapshot_each_block', True) else None
            blocks.append({
                'date_window': date_window,
                'block_id': block_id,
                'block_pattern': item['block_pattern'],
                'backend_snapshot_before_block': block_snapshot_before,
                'submissions': [],
            })
        victim_record = run_sampler_job(backend, build_victim_circuit(item['label'], cfg), shots=shots)
        entry = _record_to_dict(
            victim_record,
            block_id=block_id,
            position_in_block=int(item['position_in_block']),
            date_window=date_window,
            task_family=str(item['task_family']),
            block_pattern=str(item['block_pattern']),
        )
        entry['backend_snapshot_before_block'] = blocks[-1]['backend_snapshot_before_block']
        entry['notes'] = 'matched_paired_submission'
        blocks[-1]['submissions'].append(entry)
        records.append(entry)

    analysis = _analyze_variants(records, cfg)
    raw_metrics = analysis['raw']['metrics']
    coarse_metrics = analysis['coarse_bucket']['metrics']
    grouped_metrics = analysis['grouped_release']['metrics']
    run_end_ts = time.time()

    return {
        'run_index': run_index,
        'date_window': date_window,
        'run_start_ts': round(run_start_ts, 4),
        'run_end_ts': round(run_end_ts, 4),
        'backend_snapshot_before_run': snapshot_before,
        'backend_used': _backend_name(backend),
        'shots': shots,
        'paired_blocks': int(cfg.get('paired_blocks', cfg.get('rounds_per_class', cfg.get('victim_jobs', 4)))),
        'submissions_per_block': len(str(_block_patterns(cfg)[0])),
        'design': 'paired_blocks',
        'block_patterns': _block_patterns(cfg),
        'raw_metrics': raw_metrics,
        'coarse_bucket_metrics': coarse_metrics,
        'grouped_release_metrics': grouped_metrics,
        'raw_block_gap_summary': analysis['raw']['block_gap_summary'],
        'coarse_bucket_block_gap_summary': analysis['coarse_bucket']['block_gap_summary'],
        'grouped_release_block_gap_summary': analysis['grouped_release']['block_gap_summary'],
        'avg_victim_depth': _mean_metric(records, 'depth'),
        'avg_victim_two_qubit_gates': _mean_metric(records, 'two_qubit_gates'),
        'submission_records': records,
        'blocks': blocks,
    }


def _aggregate_variant_metrics(run_summaries: list[dict], key: str) -> dict:
    if not run_summaries:
        return {
            'mean_threshold_accuracy': 0.0,
            'mean_leakage_advantage': 0.0,
            'mean_class_gap': 0.0,
            'std_class_gap': 0.0,
            'mean_effect_size': 0.0,
            'positive_gap_ratio': 0.0,
            'direction_majority': 'unknown',
            'direction_consistency_ratio': 0.0,
        }
    metrics = [run.get(key, {}) for run in run_summaries]
    threshold = [float(x.get('threshold_accuracy', 0.0)) for x in metrics]
    leak = [float(x.get('leakage_advantage', 0.0)) for x in metrics]
    gap = [float(x.get('class_gap', 0.0)) for x in metrics]
    effect = [float(x.get('effect_size', 0.0)) for x in metrics]
    directions = [str(x.get('direction', 'unknown')) for x in metrics]
    majority = max(set(directions), key=directions.count) if directions else 'unknown'
    return {
        'mean_threshold_accuracy': round(mean(threshold), 4),
        'mean_leakage_advantage': round(mean(leak), 4),
        'mean_class_gap': round(mean(gap), 4),
        'std_class_gap': round(pstdev(gap), 4) if len(gap) > 1 else 0.0,
        'mean_effect_size': round(mean(effect), 4),
        'positive_gap_ratio': round(sum(1 for x in gap if x > 0) / max(len(gap), 1), 4),
        'direction_majority': majority,
        'direction_consistency_ratio': round(sum(1 for x in directions if x == majority) / max(len(directions), 1), 4),
    }


def _aggregate_runs(run_summaries: list[dict]) -> dict:
    if not run_summaries:
        return {
            'num_runs': 0,
            'raw': _aggregate_variant_metrics([], 'raw_metrics'),
            'coarse_bucket': _aggregate_variant_metrics([], 'coarse_bucket_metrics'),
            'grouped_release': _aggregate_variant_metrics([], 'grouped_release_metrics'),
            'raw_minus_coarse_leakage_advantage': 0.0,
            'raw_minus_grouped_leakage_advantage': 0.0,
            'raw_positive_gap_ratio': 0.0,
            'coarse_positive_gap_ratio': 0.0,
            'grouped_positive_gap_ratio': 0.0,
        }

    raw = _aggregate_variant_metrics(run_summaries, 'raw_metrics')
    coarse = _aggregate_variant_metrics(run_summaries, 'coarse_bucket_metrics')
    grouped = _aggregate_variant_metrics(run_summaries, 'grouped_release_metrics')
    return {
        'num_runs': len(run_summaries),
        'raw': raw,
        'coarse_bucket': coarse,
        'grouped_release': grouped,
        'raw_minus_coarse_leakage_advantage': round(raw['mean_leakage_advantage'] - coarse['mean_leakage_advantage'], 4),
        'raw_minus_grouped_leakage_advantage': round(raw['mean_leakage_advantage'] - grouped['mean_leakage_advantage'], 4),
        'raw_positive_gap_ratio': raw['positive_gap_ratio'],
        'coarse_positive_gap_ratio': coarse['positive_gap_ratio'],
        'grouped_positive_gap_ratio': grouped['positive_gap_ratio'],
    }


def run_once(cfg: dict) -> dict:
    try:
        service = load_service(cfg)
    except IBMRuntimeUnavailable as exc:
        return {
            'status': 'unavailable',
            'reason': str(exc),
        }

    backends = list_candidate_backends(service, max_backends=cfg.get('max_backends', 1), backend_name=cfg.get('backend_name'))
    if not backends:
        return {'status': 'unavailable', 'reason': 'No operational IBM backends available.'}

    backend = backends[0]
    num_runs = int(cfg.get('num_runs', 1))
    shots = int(cfg.get('shots', 16))
    date_window_labels = _date_window_labels(cfg, num_runs)

    run_summaries = []
    snapshots = []
    for run_index in range(num_runs):
        current_backends = list_candidate_backends(service, max_backends=cfg.get('max_backends', 1), backend_name=cfg.get('backend_name'))
        current_backend = current_backends[0] if current_backends else backend
        if cfg.get('export_backend_snapshot', True):
            snapshots.append(snapshot_backend(current_backend))
        date_window = date_window_labels[run_index % len(date_window_labels)]
        run_summaries.append(_run_single_study(service, current_backend, cfg, run_index, date_window))

    aggregate = _aggregate_runs(run_summaries)
    result = {
        'status': 'ok',
        'study_type': 'repeated_limited_hardware_timing_validation' if num_runs > 1 else 'limited_hardware_timing_validation',
        'notes': 'Repeated paired raw submissions on a public IBM backend with analysis-layer coarse/grouped observation contrasts for bounded feasibility-oriented support.',
        'backend_snapshots': snapshots,
        'backend_used': _backend_name(backend),
        'shots': shots,
        'paired_blocks': int(cfg.get('paired_blocks', cfg.get('rounds_per_class', cfg.get('victim_jobs', 4)))),
        'submissions_per_block': len(str(_block_patterns(cfg)[0])),
        'num_runs': num_runs,
        'block_patterns': _block_patterns(cfg),
        'coarse_bucket_s': float(cfg.get('coarse_bucket_s', 1.0)),
        'grouped_observation_mode': str(cfg.get('grouped_observation_mode', 'family_mean')),
        'victim_family': cfg.get('victim_family', 'legacy'),
        'aggregate': aggregate,
        'run_summaries': run_summaries,
    }

    if run_summaries:
        last = run_summaries[-1]
        result.update({
            'raw_metrics': last['raw_metrics'],
            'coarse_bucket_metrics': last['coarse_bucket_metrics'],
            'grouped_release_metrics': last['grouped_release_metrics'],
            'raw_block_gap_summary': last['raw_block_gap_summary'],
            'coarse_bucket_block_gap_summary': last['coarse_bucket_block_gap_summary'],
            'grouped_release_block_gap_summary': last['grouped_release_block_gap_summary'],
            'avg_victim_depth': last['avg_victim_depth'],
            'avg_victim_two_qubit_gates': last['avg_victim_two_qubit_gates'],
            'submission_records': last['submission_records'],
            'blocks': last['blocks'],
            'date_window': last['date_window'],
        })

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / 'timing_hardware_summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
