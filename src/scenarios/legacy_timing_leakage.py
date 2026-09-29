from __future__ import annotations

import copy
import json
import math
import random
import time
import traceback
from pathlib import Path
from statistics import mean, pstdev

from attacks.timing_probe import build_probe_job
from evaluation.aggregate import aggregate_metrics
from evaluation.statistics import summarize
from scenarios.common import build_scheduler, clone_backends
from sim.environment import SimulationEnvironment
from utils.random_seed import set_seed
from workloads.compile_aware import annotate_job_compile_features, representative_compile_catalog, resolve_compile_config
from workloads.synthetic import synthetic_job

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / 'results' / 'timing'
SWEEP_DIR = ROOT / 'results' / 'sweeps'
ABLATION_DIR = ROOT / 'results' / 'ablations'
STABILITY_DIR = ROOT / 'results' / 'stability'
PLOTS_DIR = ROOT / 'plots' / 'timing'


def _fairness_index(values: list[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    denom = len(vals) * sum(v * v for v in vals)
    if denom == 0:
        return 0.0
    return (sum(vals) ** 2) / denom


def _variance(values: list[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    if len(vals) <= 1:
        return 0.0
    mu = sum(vals) / len(vals)
    return sum((v - mu) ** 2 for v in vals) / len(vals)


def _percentile(values: list[float], q: float) -> float:
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    q = min(1.0, max(0.0, q))
    pos = q * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _entropy(labels: list[str]) -> float:
    if not labels:
        return 0.0
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    total = float(len(labels))
    out = 0.0
    for count in counts.values():
        p = count / total
        out -= p * (0.0 if p <= 0.0 else __import__('math').log2(p))
    return out


def _default_workload_profile() -> dict:
    return {
        'name': 'controlled',
        'benign_count_scale': 1.0,
        'probe_count_scale': 1.0,
        'victim_count_scale': 1.0,
        'benign_arrival_gap': 0.6,
        'victim_arrival_gap': 0.75,
        'probe_arrival_gap': 0.55,
        'benign_jitter': 0.15,
        'victim_jitter': 0.12,
        'probe_jitter': 0.06,
        'benign_depth_bias': 0,
        'victim_depth_bias': 0,
        'probe_depth_bias': 0,
        'benign_burst_every': 0,
        'benign_burst_extra': 0.0,
        'probe_start': 1.0,
        'probe_phase_stride': 22,
        'victim_start': 1.0,
        'pressure_multiplier': 1.0,
        'tenant_mode': 'stable',
        'benign_tenant_pool': 2,
        'tenant_drift_stride': 6,
        'mixed_sensitive_ratio': 0.0,
        'mixed_heavy_ratio': 0.0,
    }


def _default_victim_profiles() -> dict[str, dict]:
    return {
        'classA': {
            'base_qubits': 5,
            'base_depth': 45,
            'qubit_jitter_min': -1,
            'qubit_jitter_max': 2,
            'depth_jitter_min': -18,
            'depth_jitter_max': 24,
            'isolation_level': 'normal',
            'compile_family_pool': ['small_qaoa', 'bv_like'],
            'pressure_bias': 0.08,
        },
        'classB': {
            'base_qubits': 14,
            'base_depth': 280,
            'qubit_jitter_min': -1,
            'qubit_jitter_max': 2,
            'depth_jitter_min': -18,
            'depth_jitter_max': 24,
            'isolation_level': 'normal',
            'compile_family_pool': ['grover_like', 'random'],
            'pressure_bias': 0.55,
        },
        'highIsolation': {
            'base_qubits': 10,
            'base_depth': 170,
            'qubit_jitter_min': -1,
            'qubit_jitter_max': 2,
            'depth_jitter_min': -18,
            'depth_jitter_max': 24,
            'isolation_level': 'high',
            'compile_family_pool': ['mirror', 'grover_like'],
            'pressure_bias': 0.25,
        },
    }


def _resolve_victim_profile(cfg: dict, label: str) -> dict | None:
    defaults = _default_victim_profiles()
    configured = cfg.get('victim_profiles', {})
    if label not in defaults and label not in configured:
        return None
    profile = dict(defaults.get(label, {}))
    profile.update(configured.get(label, {}))
    if 'compile_family_pool' in profile and isinstance(profile['compile_family_pool'], str):
        profile['compile_family_pool'] = [profile['compile_family_pool']]
    return profile


def _resolve_named_profile(name: str | None, configured_profiles: dict) -> dict:
    profile = _default_workload_profile()
    if not name:
        return profile
    profile['name'] = name
    profile.update(configured_profiles.get(name, {}))
    return profile


def _resolve_workload_profile(cfg: dict) -> dict:
    configured = cfg.get('workload_profiles', {})
    explicit = cfg.get('workload_profile')
    active = cfg.get('active_workload_profile')
    selected = explicit or active
    if selected:
        profile = _resolve_named_profile(selected, configured)
        for key in profile:
            if key in cfg and key not in {'name'}:
                profile[key] = cfg[key]
        return profile
    profile = _default_workload_profile()
    for key in profile:
        if key in cfg:
            profile[key] = cfg[key]
    return profile


def _build_victim_jobs(label: str, count: int, rng: random.Random, cfg: dict):
    jobs = []
    profile = _resolve_victim_profile(cfg, label)
    if profile is None:
        return jobs
    base_qubits = int(profile.get('base_qubits', 5))
    base_depth = int(profile.get('base_depth', 45))
    isolation = str(profile.get('isolation_level', 'normal'))
    qubit_jitter_min = int(profile.get('qubit_jitter_min', -1))
    qubit_jitter_max = int(profile.get('qubit_jitter_max', 2))
    depth_jitter_min = int(profile.get('depth_jitter_min', -18))
    depth_jitter_max = int(profile.get('depth_jitter_max', 24))
    compile_family_pool = profile.get('compile_family_pool')
    pressure_bias = float(profile.get('pressure_bias', 0.0))
    for i in range(count):
        t = i * 0.75 + 1.0 + rng.uniform(-0.12, 0.12)
        job = synthetic_job(
            f'{label}-victim-{i}',
            'victim',
            float(max(0.0, t)),
            max(4, base_qubits + rng.randint(qubit_jitter_min, qubit_jitter_max)),
            max(30, base_depth + rng.randint(depth_jitter_min, depth_jitter_max)),
            workload_tag=label,
        )
        job.metadata.isolation_level = isolation
        job.metadata.notes['pressure_bias'] = pressure_bias
        if compile_family_pool:
            job.metadata.notes['compile_family_pool'] = list(compile_family_pool)
        jobs.append(job)
    return jobs


def _stats_options(cfg: dict) -> dict:
    return {
        'ci_method': cfg.get('ci_method', 'normal'),
        'bootstrap_iterations': int(cfg.get('bootstrap_iterations', 2000)),
        'bootstrap_seed': int(cfg.get('bootstrap_seed', 0)),
    }


def _observation_mode_from_space(space: str) -> str:
    if space == 'O_ext':
        return 'external_only'
    if space == 'O_sb':
        return 'scheduler_boundary'
    return 'full'


def _build_backend_vocab(items: list[dict]) -> list[str]:
    vocab = sorted({str(item.get('backend_id', 'masked')) for item in items if str(item.get('backend_id', 'masked')) != 'masked'})
    return vocab


def _backend_vector(item: dict, backend_encoding: str = 'onehot', backend_vocab: list[str] | None = None) -> list[float]:
    backend_id = str(item.get('backend_id', 'masked'))
    if backend_encoding == 'hash':
        return [float(sum(ord(c) for c in backend_id) % 7)]
    vocab = backend_vocab or []
    if backend_id == 'masked' or not vocab:
        return [0.0 for _ in vocab]
    return [1.0 if backend_id == entry else 0.0 for entry in vocab]


def _base_features(
    item: dict,
    *,
    observation_space: str = 'O_sb',
    backend_encoding: str = 'onehot',
    backend_vocab: list[str] | None = None,
    public_feature_set: str = 'wait_backend',
) -> list[float]:
    observed_wait = float(item.get('observed_wait', 0.0))
    queue_length = float(item.get('queue_length', 0.0))
    score_margin = float(item.get('score_margin', 0.0))
    public_status = float(item.get('public_status', 0.0))
    backend_feats = _backend_vector(item, backend_encoding=backend_encoding, backend_vocab=backend_vocab)
    if observation_space == 'O_ext':
        if public_feature_set == 'wait_only':
            return [observed_wait]
        if public_feature_set == 'wait_status':
            return [observed_wait, public_status]
        if public_feature_set == 'wait_status_backend':
            return [observed_wait, public_status] + backend_feats
        return [observed_wait] + backend_feats
    if observation_space == 'O_int':
        return [observed_wait, queue_length, score_margin] + backend_feats
    return [observed_wait, queue_length, score_margin] + backend_feats


def _feature_vector(
    item: dict,
    feature_mode: str = 'base',
    *,
    observation_space: str = 'O_sb',
    backend_encoding: str = 'onehot',
    backend_vocab: list[str] | None = None,
    public_feature_set: str = 'wait_backend',
) -> list[float]:
    base = _base_features(
        item,
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        backend_vocab=backend_vocab,
        public_feature_set=public_feature_set,
    )
    logical = [
        float(item.get('logical_qubits', 0.0)),
        float(item.get('logical_depth', 0.0)),
    ]
    compile_visible = [
        float(item.get('compiled_depth', 0.0)),
        float(item.get('cx_count', 0.0)),
        float(item.get('swap_count', 0.0)),
        float(item.get('layout_span', 0.0)),
        float(item.get('expected_fidelity', 0.0)),
        float(item.get('backend_suitability', 0.0)),
    ]
    if feature_mode == 'backend_only':
        return _backend_vector(item, backend_encoding=backend_encoding, backend_vocab=backend_vocab)
    if feature_mode == 'logical_only':
        return base + logical
    if feature_mode == 'compile_visible':
        return base + compile_visible
    if feature_mode == 'shuffled_compile':
        return base + [
            float(item.get('shuffled_compiled_depth', 0.0)),
            float(item.get('shuffled_cx_count', 0.0)),
            float(item.get('shuffled_swap_count', 0.0)),
            float(item.get('shuffled_layout_span', 0.0)),
            float(item.get('shuffled_expected_fidelity', 0.0)),
            float(item.get('shuffled_backend_suitability', 0.0)),
        ]
    if feature_mode == 'random_matched':
        return base + [
            float(item.get('random_compiled_depth', 0.0)),
            float(item.get('random_cx_count', 0.0)),
            float(item.get('random_swap_count', 0.0)),
            float(item.get('random_layout_span', 0.0)),
            float(item.get('random_expected_fidelity', 0.0)),
            float(item.get('random_backend_suitability', 0.0)),
        ]
    return base


def _stats(
    items: list[dict],
    feature_mode: str = 'base',
    *,
    observation_space: str = 'O_sb',
    backend_encoding: str = 'onehot',
    backend_vocab: list[str] | None = None,
    public_feature_set: str = 'wait_backend',
) -> tuple[list[float], list[float]]:
    feats = [
        _feature_vector(
            x,
            feature_mode=feature_mode,
            observation_space=observation_space,
            backend_encoding=backend_encoding,
            backend_vocab=backend_vocab,
            public_feature_set=public_feature_set,
        )
        for x in items
    ]
    dims = len(feats[0])
    means = [sum(f[i] for f in feats) / len(feats) for i in range(dims)]
    stds = []
    for i in range(dims):
        var = sum((f[i] - means[i]) ** 2 for f in feats) / len(feats)
        stds.append(var ** 0.5 if var > 1e-9 else 1.0)
    return means, stds


def _normalize(vec, means, stds):
    return [(x - m) / s for x, m, s in zip(vec, means, stds)]


def _split_holdout(class_a: list[dict], class_b: list[dict], seed: int) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    a = list(class_a)
    b = list(class_b)
    rng.shuffle(a)
    rng.shuffle(b)
    split_a = max(1, len(a) // 2)
    split_b = max(1, len(b) // 2)
    train_a, test_a = a[:split_a], a[split_a:]
    train_b, test_b = b[:split_b], b[split_b:]
    if not test_a:
        test_a = train_a
    if not test_b:
        test_b = train_b
    return train_a, test_a, train_b, test_b


def _threshold_classifier(class_a: list[dict], class_b: list[dict], seed: int) -> dict:
    train_a, test_a, train_b, test_b = _split_holdout(class_a, class_b, seed)
    a = [x.get('observed_wait', 0.0) for x in train_a]
    b = [x.get('observed_wait', 0.0) for x in train_b]
    thr = (mean(a) + mean(b)) / 2.0 if a and b else 0.0
    correct = sum(int(x.get('observed_wait', 0.0) < thr) for x in test_a) + sum(int(x.get('observed_wait', 0.0) >= thr) for x in test_b)
    total = len(test_a) + len(test_b)
    acc = correct / total if total else 0.0
    return {'threshold_accuracy': round(acc, 4), 'threshold_leakage_advantage': round(acc - 0.5, 4)}


def _linear_classifier(
    class_a: list[dict],
    class_b: list[dict],
    seed: int,
    feature_mode: str = 'base',
    *,
    observation_space: str = 'O_sb',
    backend_encoding: str = 'onehot',
    public_feature_set: str = 'wait_backend',
) -> dict:
    train_a, test_a, train_b, test_b = _split_holdout(class_a, class_b, seed)
    backend_vocab = _build_backend_vocab(train_a + train_b + test_a + test_b)
    means, stds = _stats(
        train_a + train_b,
        feature_mode=feature_mode,
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        backend_vocab=backend_vocab,
        public_feature_set=public_feature_set,
    )
    norm_a = [
        _normalize(
            _feature_vector(
                x,
                feature_mode=feature_mode,
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                backend_vocab=backend_vocab,
                public_feature_set=public_feature_set,
            ),
            means,
            stds,
        )
        for x in train_a
    ]
    norm_b = [
        _normalize(
            _feature_vector(
                x,
                feature_mode=feature_mode,
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                backend_vocab=backend_vocab,
                public_feature_set=public_feature_set,
            ),
            means,
            stds,
        )
        for x in train_b
    ]
    mu_a = [sum(v[i] for v in norm_a) / len(norm_a) for i in range(len(norm_a[0]))]
    mu_b = [sum(v[i] for v in norm_b) / len(norm_b) for i in range(len(norm_b[0]))]
    w = [b - a for a, b in zip(mu_a, mu_b)]
    midpoint = [(a + b) / 2.0 for a, b in zip(mu_a, mu_b)]
    bias = -sum(wi * mi for wi, mi in zip(w, midpoint))

    def score(item):
        vec = _normalize(
            _feature_vector(
                item,
                feature_mode=feature_mode,
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                backend_vocab=backend_vocab,
                public_feature_set=public_feature_set,
            ),
            means,
            stds,
        )
        return sum(x * wi for x, wi in zip(vec, w)) + bias

    correct = sum(int(score(x) < 0) for x in test_a) + sum(int(score(x) >= 0) for x in test_b)
    total = len(test_a) + len(test_b)
    acc = correct / total if total else 0.0
    return {'accuracy': round(acc, 4), 'leakage_advantage': round(acc - 0.5, 4)}


def _seed_grouped_dataset(runs: list[dict], left: str, right: str) -> tuple[list[dict], list[dict]]:
    class_a: list[dict] = []
    class_b: list[dict] = []
    for run in runs:
        seed = int(run['seed'])
        for item in run['scenarios'][left]['probe_traces']:
            entry = dict(item)
            entry['_group_seed'] = seed
            class_a.append(entry)
        for item in run['scenarios'][right]['probe_traces']:
            entry = dict(item)
            entry['_group_seed'] = seed
            class_b.append(entry)
    return class_a, class_b


def _grouped_splits(class_a: list[dict], class_b: list[dict], split_mode: str, seed: int) -> list[tuple[set[int], set[int]]]:
    groups = sorted({int(item['_group_seed']) for item in class_a + class_b})
    if not groups:
        return []
    if split_mode == 'leave_one_seed_out':
        return [({g for g in groups if g != heldout}, {heldout}) for heldout in groups]
    rng = random.Random(seed)
    shuffled = list(groups)
    rng.shuffle(shuffled)
    cut = max(1, len(shuffled) // 2)
    train = set(shuffled[:cut])
    test = set(shuffled[cut:]) or set(shuffled[:1])
    if not train:
        train = set(test)
    return [(train, test)]


def _filter_groups(items: list[dict], groups: set[int]) -> list[dict]:
    return [item for item in items if int(item.get('_group_seed', -1)) in groups]


def _grouped_classifier_summary(
    class_a: list[dict],
    class_b: list[dict],
    *,
    split_mode: str,
    seed: int,
    feature_mode: str,
    observation_space: str,
    backend_encoding: str,
    stats_options: dict,
    public_feature_set: str,
) -> dict:
    splits = _grouped_splits(class_a, class_b, split_mode, seed)
    accuracies: list[float] = []
    thresholds: list[float] = []
    for train_groups, test_groups in splits:
        train_a = _filter_groups(class_a, train_groups)
        train_b = _filter_groups(class_b, train_groups)
        test_a = _filter_groups(class_a, test_groups)
        test_b = _filter_groups(class_b, test_groups)
        if not train_a or not train_b or not test_a or not test_b:
            continue
        backend_vocab = _build_backend_vocab(train_a + train_b + test_a + test_b)
        means, stds = _stats(
            train_a + train_b,
            feature_mode=feature_mode,
            observation_space=observation_space,
            backend_encoding=backend_encoding,
            backend_vocab=backend_vocab,
            public_feature_set=public_feature_set,
        )
        norm_a = [
            _normalize(
                _feature_vector(
                    x,
                    feature_mode=feature_mode,
                    observation_space=observation_space,
                    backend_encoding=backend_encoding,
                    backend_vocab=backend_vocab,
                    public_feature_set=public_feature_set,
                ),
                means,
                stds,
            )
            for x in train_a
        ]
        norm_b = [
            _normalize(
                _feature_vector(
                    x,
                    feature_mode=feature_mode,
                    observation_space=observation_space,
                    backend_encoding=backend_encoding,
                    backend_vocab=backend_vocab,
                    public_feature_set=public_feature_set,
                ),
                means,
                stds,
            )
            for x in train_b
        ]
        mu_a = [sum(v[i] for v in norm_a) / len(norm_a) for i in range(len(norm_a[0]))]
        mu_b = [sum(v[i] for v in norm_b) / len(norm_b) for i in range(len(norm_b[0]))]
        w = [b - a for a, b in zip(mu_a, mu_b)]
        midpoint = [(a + b) / 2.0 for a, b in zip(mu_a, mu_b)]
        bias = -sum(wi * mi for wi, mi in zip(w, midpoint))

        def score(item: dict) -> float:
            vec = _normalize(
                _feature_vector(
                    item,
                    feature_mode=feature_mode,
                    observation_space=observation_space,
                    backend_encoding=backend_encoding,
                    backend_vocab=backend_vocab,
                    public_feature_set=public_feature_set,
                ),
                means,
                stds,
            )
            return sum(x * wi for x, wi in zip(vec, w)) + bias

        correct = sum(int(score(x) < 0) for x in test_a) + sum(int(score(x) >= 0) for x in test_b)
        total = len(test_a) + len(test_b)
        if total:
            accuracies.append(correct / total)

        thr = (mean([x.get('observed_wait', 0.0) for x in train_a]) + mean([x.get('observed_wait', 0.0) for x in train_b])) / 2.0
        thr_correct = sum(int(x.get('observed_wait', 0.0) < thr) for x in test_a) + sum(int(x.get('observed_wait', 0.0) >= thr) for x in test_b)
        thresholds.append(thr_correct / total if total else 0.0)

    acc_summary = summarize(accuracies, **stats_options) if accuracies else summarize([], **stats_options)
    thr_summary = summarize(thresholds, **stats_options) if thresholds else summarize([], **stats_options)
    return {
        'accuracy': acc_summary,
        'leakage_advantage': summarize([x - 0.5 for x in accuracies], **stats_options) if accuracies else summarize([], **stats_options),
        'threshold_accuracy': thr_summary,
        'threshold_leakage_advantage': summarize([x - 0.5 for x in thresholds], **stats_options) if thresholds else summarize([], **stats_options),
    }


def _sequence_summary_features(values: list[float]) -> list[float]:
    vals = [float(v) for v in values]
    if not vals:
        return [0.0] * 7
    return [
        round(mean(vals), 6),
        round(pstdev(vals), 6) if len(vals) > 1 else 0.0,
        round(min(vals), 6),
        round(max(vals), 6),
        round(_percentile(vals, 0.25), 6),
        round(_percentile(vals, 0.5), 6),
        round(_percentile(vals, 0.75), 6),
    ]


def _bundle_vector(
    traces: list[dict],
    *,
    budget: int,
    observation_space: str,
    backend_encoding: str,
    public_feature_set: str,
) -> list[float]:
    bundle = list(traces[: max(1, int(budget))])
    waits = [float(item.get('observed_wait', 0.0)) for item in bundle]
    queue_lengths = [float(item.get('queue_length', 0.0)) for item in bundle]
    public_statuses = [float(item.get('public_status', 0.0)) for item in bundle]
    score_margins = [float(item.get('score_margin', 0.0)) for item in bundle]
    features: list[float] = []
    if observation_space == 'O_ext':
        features.extend(_sequence_summary_features(waits))
        if public_feature_set == 'wait_status':
            features.extend(_sequence_summary_features(public_statuses))
        elif public_feature_set == 'wait_backend':
            backend_vocab = _build_backend_vocab(bundle)
            if backend_encoding == 'onehot' and backend_vocab:
                for backend_id in backend_vocab:
                    share = sum(1.0 for item in bundle if str(item.get('backend_id', 'masked')) == backend_id) / len(bundle)
                    features.append(round(share, 6))
        return features
    features.extend(_sequence_summary_features(waits))
    features.extend(_sequence_summary_features(queue_lengths))
    features.extend(_sequence_summary_features(score_margins))
    if public_feature_set != 'wait_only':
        features.extend(_sequence_summary_features(public_statuses))
    if public_feature_set == 'wait_backend':
        backend_vocab = _build_backend_vocab(bundle)
        if backend_encoding == 'onehot' and backend_vocab:
            for backend_id in backend_vocab:
                share = sum(1.0 for item in bundle if str(item.get('backend_id', 'masked')) == backend_id) / len(bundle)
                features.append(round(share, 6))
    return features


def _bundle_dataset_from_runs(
    runs: list[dict],
    left: str,
    right: str,
    *,
    budget: int,
    observation_space: str,
    backend_encoding: str,
    public_feature_set: str,
) -> tuple[list[dict], list[dict]]:
    class_a: list[dict] = []
    class_b: list[dict] = []
    for run in runs:
        seed = int(run['seed'])
        left_traces = list(run['scenarios'][left]['probe_traces'])
        right_traces = list(run['scenarios'][right]['probe_traces'])
        class_a.append({
            '_group_seed': seed,
            'bundle_vector': _bundle_vector(
                left_traces,
                budget=budget,
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            'bundle_mean_wait': round(mean(float(item.get('observed_wait', 0.0)) for item in left_traces[:budget]), 6),
            'bundle_size': min(len(left_traces), int(budget)),
        })
        class_b.append({
            '_group_seed': seed,
            'bundle_vector': _bundle_vector(
                right_traces,
                budget=budget,
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            'bundle_mean_wait': round(mean(float(item.get('observed_wait', 0.0)) for item in right_traces[:budget]), 6),
            'bundle_size': min(len(right_traces), int(budget)),
        })
    return class_a, class_b


def _bundle_classifier_summary(
    class_a: list[dict],
    class_b: list[dict],
    *,
    split_mode: str,
    seed: int,
    stats_options: dict,
) -> dict:
    splits = _grouped_splits(class_a, class_b, split_mode, seed)
    accuracies: list[float] = []
    thresholds: list[float] = []
    for train_groups, test_groups in splits:
        train_a = _filter_groups(class_a, train_groups)
        train_b = _filter_groups(class_b, train_groups)
        test_a = _filter_groups(class_a, test_groups)
        test_b = _filter_groups(class_b, test_groups)
        if not train_a or not train_b or not test_a or not test_b:
            continue
        dim = len(train_a[0]['bundle_vector'])
        means = []
        stds = []
        for idx in range(dim):
            column = [float(item['bundle_vector'][idx]) for item in train_a + train_b]
            mu = sum(column) / len(column)
            sigma = (sum((value - mu) ** 2 for value in column) / len(column)) ** 0.5
            means.append(mu)
            stds.append(sigma if sigma > 1e-9 else 1.0)

        def normalize(vec: list[float]) -> list[float]:
            return [(value - mu) / sigma for value, mu, sigma in zip(vec, means, stds)]

        norm_a = [normalize(item['bundle_vector']) for item in train_a]
        norm_b = [normalize(item['bundle_vector']) for item in train_b]
        mu_a = [sum(v[idx] for v in norm_a) / len(norm_a) for idx in range(dim)]
        mu_b = [sum(v[idx] for v in norm_b) / len(norm_b) for idx in range(dim)]
        w = [b - a for a, b in zip(mu_a, mu_b)]
        midpoint = [(a + b) / 2.0 for a, b in zip(mu_a, mu_b)]
        bias = -sum(wi * mi for wi, mi in zip(w, midpoint))

        def score(item: dict) -> float:
            vec = normalize(item['bundle_vector'])
            return sum(value * weight for value, weight in zip(vec, w)) + bias

        correct = sum(int(score(item) < 0) for item in test_a) + sum(int(score(item) >= 0) for item in test_b)
        total = len(test_a) + len(test_b)
        if total:
            accuracies.append(correct / total)

        thr = (
            mean(float(item.get('bundle_mean_wait', 0.0)) for item in train_a)
            + mean(float(item.get('bundle_mean_wait', 0.0)) for item in train_b)
        ) / 2.0
        thr_correct = sum(int(float(item.get('bundle_mean_wait', 0.0)) < thr) for item in test_a) + sum(
            int(float(item.get('bundle_mean_wait', 0.0)) >= thr) for item in test_b
        )
        thresholds.append(thr_correct / total if total else 0.0)

    acc_summary = summarize(accuracies, **stats_options) if accuracies else summarize([], **stats_options)
    thr_summary = summarize(thresholds, **stats_options) if thresholds else summarize([], **stats_options)
    return {
        'accuracy': acc_summary,
        'leakage_advantage': summarize([x - 0.5 for x in accuracies], **stats_options) if accuracies else summarize([], **stats_options),
        'threshold_accuracy': thr_summary,
        'threshold_leakage_advantage': summarize([x - 0.5 for x in thresholds], **stats_options) if thresholds else summarize([], **stats_options),
        'num_bundle_samples_per_class': len(class_a),
    }


def _swap_class_labels_in_run(run: dict) -> dict:
    swapped = copy.deepcopy(run)
    for left, right in [('classA', 'classB'), ('classA_defended', 'classB_defended')]:
        if left in swapped.get('scenarios', {}) and right in swapped.get('scenarios', {}):
            swapped['scenarios'][left], swapped['scenarios'][right] = swapped['scenarios'][right], swapped['scenarios'][left]
    for left_key, right_key in [('classA_mean_wait', 'classB_mean_wait'), ('classA_minus_noVictim', 'classB_minus_noVictim')]:
        if left_key in swapped and right_key in swapped:
            swapped[left_key], swapped[right_key] = swapped[right_key], swapped[left_key]
    return swapped


def _resampled_runs_with_new_seeds(runs: list[dict], sampled_indices: list[int]) -> list[dict]:
    resampled: list[dict] = []
    for new_seed, run_index in enumerate(sampled_indices):
        cloned = copy.deepcopy(runs[run_index])
        cloned['seed'] = new_seed
        resampled.append(cloned)
    return resampled


def _prepare_seed_trace_groups(runs: list[dict]) -> dict[int, dict[str, list[dict]]]:
    prepared: dict[int, dict[str, list[dict]]] = {}
    for run in runs:
        seed = int(run['seed'])
        prepared[seed] = {}
        for scenario_name in ['classA', 'classB', 'classA_defended', 'classB_defended']:
            traces = []
            for item in run['scenarios'][scenario_name]['probe_traces']:
                entry = dict(item)
                entry['_group_seed'] = seed
                traces.append(entry)
            prepared[seed][scenario_name] = traces
    return prepared


def _prepare_seed_bundle_groups(runs: list[dict], cfg: dict, budgets: list[int]) -> dict[str, dict[int, dict[str, dict]]]:
    observation_space = cfg.get('observation_space', 'O_ext')
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    public_feature_set = cfg.get('public_feature_set', 'wait_only')
    prepared: dict[str, dict[int, dict[str, dict]]] = {str(budget): {} for budget in budgets}
    for run in runs:
        seed = int(run['seed'])
        for budget in budgets:
            budget_key = str(budget)
            prepared[budget_key][seed] = {}
            for scenario_name in ['classA', 'classB', 'classA_defended', 'classB_defended']:
                traces = list(run['scenarios'][scenario_name]['probe_traces'])
                prepared[budget_key][seed][scenario_name] = {
                    '_group_seed': seed,
                    'bundle_vector': _bundle_vector(
                        traces,
                        budget=int(budget),
                        observation_space=observation_space,
                        backend_encoding=backend_encoding,
                        public_feature_set=public_feature_set,
                    ),
                    'bundle_mean_wait': round(mean(float(item.get('observed_wait', 0.0)) for item in traces[:budget]), 6),
                    'bundle_size': min(len(traces), int(budget)),
                }
    return prepared


def _relabel_seed_trace_groups(
    prepared: dict[int, dict[str, list[dict]]],
    *,
    swap_flags: dict[int, bool] | None = None,
    sampled_seed_order: list[int] | None = None,
) -> dict[str, list[dict]]:
    if sampled_seed_order is None:
        sampled_seed_order = sorted(prepared)
        preserve_seed_ids = True
    else:
        preserve_seed_ids = False
    class_a_raw: list[dict] = []
    class_b_raw: list[dict] = []
    class_a_def: list[dict] = []
    class_b_def: list[dict] = []
    for new_seed, original_seed in enumerate(sampled_seed_order):
        swap = bool((swap_flags or {}).get(original_seed, False))
        source = prepared[original_seed]
        raw_left = source['classB'] if swap else source['classA']
        raw_right = source['classA'] if swap else source['classB']
        def_left = source['classB_defended'] if swap else source['classA_defended']
        def_right = source['classA_defended'] if swap else source['classB_defended']
        target_seed = original_seed if preserve_seed_ids else new_seed
        if preserve_seed_ids:
            class_a_raw.extend(raw_left)
            class_b_raw.extend(raw_right)
            class_a_def.extend(def_left)
            class_b_def.extend(def_right)
            continue
        class_a_raw.extend([{**item, '_group_seed': target_seed} for item in raw_left])
        class_b_raw.extend([{**item, '_group_seed': target_seed} for item in raw_right])
        class_a_def.extend([{**item, '_group_seed': target_seed} for item in def_left])
        class_b_def.extend([{**item, '_group_seed': target_seed} for item in def_right])
    return {
        'classA': class_a_raw,
        'classB': class_b_raw,
        'classA_defended': class_a_def,
        'classB_defended': class_b_def,
    }


def _relabel_seed_bundle_groups(
    prepared: dict[str, dict[int, dict[str, dict]]],
    *,
    swap_flags: dict[int, bool] | None = None,
    sampled_seed_order: list[int] | None = None,
) -> dict[str, dict[str, list[dict]]]:
    output: dict[str, dict[str, list[dict]]] = {}
    for budget_key, per_seed in prepared.items():
        if sampled_seed_order is None:
            sampled = sorted(per_seed)
            preserve_seed_ids = True
        else:
            sampled = sampled_seed_order
            preserve_seed_ids = False
        bundle_a: list[dict] = []
        bundle_b: list[dict] = []
        bundle_a_def: list[dict] = []
        bundle_b_def: list[dict] = []
        for new_seed, original_seed in enumerate(sampled):
            swap = bool((swap_flags or {}).get(original_seed, False))
            source = per_seed[original_seed]
            raw_left = source['classB'] if swap else source['classA']
            raw_right = source['classA'] if swap else source['classB']
            def_left = source['classB_defended'] if swap else source['classA_defended']
            def_right = source['classA_defended'] if swap else source['classB_defended']
            target_seed = original_seed if preserve_seed_ids else new_seed
            if preserve_seed_ids:
                bundle_a.append(raw_left)
                bundle_b.append(raw_right)
                bundle_a_def.append(def_left)
                bundle_b_def.append(def_right)
                continue
            bundle_a.append({**raw_left, '_group_seed': target_seed})
            bundle_b.append({**raw_right, '_group_seed': target_seed})
            bundle_a_def.append({**def_left, '_group_seed': target_seed})
            bundle_b_def.append({**def_right, '_group_seed': target_seed})
        output[budget_key] = {
            'classA': bundle_a,
            'classB': bundle_b,
            'classA_defended': bundle_a_def,
            'classB_defended': bundle_b_def,
        }
    return output


def _distribution_summary(values: list[float]) -> dict:
    if not values:
        return {
            'mean': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0,
            'ci95_low': 0.0,
            'ci95_high': 0.0,
        }
    return {
        'mean': round(mean(values), 4),
        'std': round(pstdev(values), 4) if len(values) > 1 else 0.0,
        'min': round(min(values), 4),
        'max': round(max(values), 4),
        'ci95_low': round(_percentile(values, 0.025), 4),
        'ci95_high': round(_percentile(values, 0.975), 4),
    }


def _two_sided_permutation_pvalue(observed: float, null_values: list[float]) -> float:
    if not null_values:
        return 1.0
    extreme = sum(1 for value in null_values if abs(value) >= abs(observed))
    return round((extreme + 1) / (len(null_values) + 1), 4)


def _write_significance_checkpoint(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _blank_significance_distribution(bundle_keys: list[str]) -> dict:
    return {
        'trace_level_raw_leakage_advantage': [],
        'trace_level_defended_leakage_advantage': [],
        'trace_level_defense_gain': [],
        'bundle_level': {
            budget: {
                'raw_leakage_advantage': [],
                'defended_leakage_advantage': [],
                'defense_gain': [],
            }
            for budget in bundle_keys
        },
    }


def _load_significance_phase_state(path: Path, template: dict) -> tuple[dict, int]:
    if not path.exists():
        return copy.deepcopy(template), 0
    payload = json.loads(path.read_text(encoding='utf-8'))
    completed = int(payload.get('completed_iterations', 0))
    values = payload.get('values', {})
    merged = copy.deepcopy(template)
    merged['trace_level_raw_leakage_advantage'] = list(values.get('trace_level_raw_leakage_advantage', []))
    merged['trace_level_defended_leakage_advantage'] = list(values.get('trace_level_defended_leakage_advantage', []))
    merged['trace_level_defense_gain'] = list(values.get('trace_level_defense_gain', []))
    for budget in merged['bundle_level']:
        budget_values = values.get('bundle_level', {}).get(budget, {})
        merged['bundle_level'][budget]['raw_leakage_advantage'] = list(budget_values.get('raw_leakage_advantage', []))
        merged['bundle_level'][budget]['defended_leakage_advantage'] = list(budget_values.get('defended_leakage_advantage', []))
        merged['bundle_level'][budget]['defense_gain'] = list(budget_values.get('defense_gain', []))
    return merged, completed


def _save_significance_phase_state(
    path: Path,
    *,
    phase: str,
    completed_iterations: int,
    total_iterations: int,
    values: dict,
    elapsed_seconds: float,
    status: str,
) -> None:
    _write_significance_checkpoint(path, {
        'status': status,
        'phase': phase,
        'completed_iterations': completed_iterations,
        'total_iterations': total_iterations,
        'elapsed_seconds': round(elapsed_seconds, 2),
        'values': values,
    })


def _significance_phase_output(
    observed: dict,
    phase_values: dict,
    *,
    phase_name: str,
    iterations: int,
    seed: int,
    mode: str,
) -> dict:
    if mode == 'permutation':
        trace_key = 'null_distribution'
        bundle_key = 'null_distribution'
        pvalue_key = 'p_value_two_sided'
    else:
        trace_key = 'bootstrap_distribution'
        bundle_key = 'bootstrap_distribution'
        pvalue_key = None

    output = {
        'iterations': iterations,
        'seed': seed,
        'trace_level': {
            'raw_leakage_advantage': {
                'observed': observed['trace_level']['raw']['leakage_advantage']['mean'],
                trace_key: _distribution_summary(phase_values['trace_level_raw_leakage_advantage']),
            },
            'defended_leakage_advantage': {
                'observed': observed['trace_level']['defended']['leakage_advantage']['mean'],
                trace_key: _distribution_summary(phase_values['trace_level_defended_leakage_advantage']),
            },
            'defense_gain': {
                'observed': observed['trace_level']['defense_gain'],
                trace_key: _distribution_summary(phase_values['trace_level_defense_gain']),
            },
        },
        'bundle_level': {},
    }
    if pvalue_key:
        output['trace_level']['raw_leakage_advantage'][pvalue_key] = _two_sided_permutation_pvalue(
            observed['trace_level']['raw']['leakage_advantage']['mean'],
            phase_values['trace_level_raw_leakage_advantage'],
        )
        output['trace_level']['defended_leakage_advantage'][pvalue_key] = _two_sided_permutation_pvalue(
            observed['trace_level']['defended']['leakage_advantage']['mean'],
            phase_values['trace_level_defended_leakage_advantage'],
        )
        output['trace_level']['defense_gain'][pvalue_key] = _two_sided_permutation_pvalue(
            observed['trace_level']['defense_gain'],
            phase_values['trace_level_defense_gain'],
        )

    for budget in observed['bundle_level']:
        output['bundle_level'][budget] = {
            'raw_leakage_advantage': {
                'observed': observed['bundle_level'][budget]['raw']['leakage_advantage']['mean'],
                bundle_key: _distribution_summary(phase_values['bundle_level'][budget]['raw_leakage_advantage']),
            },
            'defended_leakage_advantage': {
                'observed': observed['bundle_level'][budget]['defended']['leakage_advantage']['mean'],
                bundle_key: _distribution_summary(phase_values['bundle_level'][budget]['defended_leakage_advantage']),
            },
            'defense_gain': {
                'observed': observed['bundle_level'][budget]['defense_gain'],
                bundle_key: _distribution_summary(phase_values['bundle_level'][budget]['defense_gain']),
            },
        }
        if pvalue_key:
            output['bundle_level'][budget]['raw_leakage_advantage'][pvalue_key] = _two_sided_permutation_pvalue(
                observed['bundle_level'][budget]['raw']['leakage_advantage']['mean'],
                phase_values['bundle_level'][budget]['raw_leakage_advantage'],
            )
            output['bundle_level'][budget]['defended_leakage_advantage'][pvalue_key] = _two_sided_permutation_pvalue(
                observed['bundle_level'][budget]['defended']['leakage_advantage']['mean'],
                phase_values['bundle_level'][budget]['defended_leakage_advantage'],
            )
            output['bundle_level'][budget]['defense_gain'][pvalue_key] = _two_sided_permutation_pvalue(
                observed['bundle_level'][budget]['defense_gain'],
                phase_values['bundle_level'][budget]['defense_gain'],
            )
    return output


def _significance_views_from_runs(runs: list[dict], cfg: dict) -> dict:
    stats_options = _stats_options(cfg)
    split_mode = cfg.get('evaluation_split_mode', 'leave_one_seed_out')
    grouped_seed = int(cfg.get('grouped_split_seed', 0))
    observation_space = cfg.get('observation_space', 'O_ext')
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    public_feature_set = cfg.get('public_feature_set', 'wait_only')
    bundle_budgets = list(cfg.get('probe_budgets_for_significance', cfg.get('probe_budgets', [1, 5, 10, 20, 50, 220])))

    trace_raw = _grouped_classifier_summary(
        *_seed_grouped_dataset(runs, 'classA', 'classB'),
        split_mode=split_mode,
        seed=grouped_seed,
        feature_mode=cfg.get('feature_mode', 'base'),
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        stats_options=stats_options,
        public_feature_set=public_feature_set,
    )
    trace_def = _grouped_classifier_summary(
        *_seed_grouped_dataset(runs, 'classA_defended', 'classB_defended'),
        split_mode=split_mode,
        seed=grouped_seed,
        feature_mode=cfg.get('feature_mode', 'base'),
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        stats_options=stats_options,
        public_feature_set=public_feature_set,
    )

    bundle = {}
    for budget in bundle_budgets:
        bundle_raw = _bundle_classifier_summary(
            *_bundle_dataset_from_runs(
                runs,
                'classA',
                'classB',
                budget=int(budget),
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        bundle_def = _bundle_classifier_summary(
            *_bundle_dataset_from_runs(
                runs,
                'classA_defended',
                'classB_defended',
                budget=int(budget),
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        bundle[str(budget)] = {
            'raw': bundle_raw,
            'defended': bundle_def,
            'defense_gain': round(bundle_raw['leakage_advantage']['mean'] - bundle_def['leakage_advantage']['mean'], 4),
        }

    return {
        'trace_level': {
            'raw': trace_raw,
            'defended': trace_def,
            'defense_gain': round(trace_raw['leakage_advantage']['mean'] - trace_def['leakage_advantage']['mean'], 4),
        },
        'bundle_level': bundle,
    }


def _significance_views_from_prepared(
    trace_groups: dict[str, list[dict]],
    bundle_groups: dict[str, dict[str, list[dict]]],
    cfg: dict,
) -> dict:
    stats_options = _stats_options(cfg)
    split_mode = cfg.get('evaluation_split_mode', 'leave_one_seed_out')
    grouped_seed = int(cfg.get('grouped_split_seed', 0))
    observation_space = cfg.get('observation_space', 'O_ext')
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    public_feature_set = cfg.get('public_feature_set', 'wait_only')

    trace_raw = _grouped_classifier_summary(
        trace_groups['classA'],
        trace_groups['classB'],
        split_mode=split_mode,
        seed=grouped_seed,
        feature_mode=cfg.get('feature_mode', 'base'),
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        stats_options=stats_options,
        public_feature_set=public_feature_set,
    )
    trace_def = _grouped_classifier_summary(
        trace_groups['classA_defended'],
        trace_groups['classB_defended'],
        split_mode=split_mode,
        seed=grouped_seed,
        feature_mode=cfg.get('feature_mode', 'base'),
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        stats_options=stats_options,
        public_feature_set=public_feature_set,
    )

    bundle: dict[str, dict] = {}
    for budget_key, budget_groups in bundle_groups.items():
        bundle_raw = _bundle_classifier_summary(
            budget_groups['classA'],
            budget_groups['classB'],
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        bundle_def = _bundle_classifier_summary(
            budget_groups['classA_defended'],
            budget_groups['classB_defended'],
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        bundle[budget_key] = {
            'raw': bundle_raw,
            'defended': bundle_def,
            'defense_gain': round(bundle_raw['leakage_advantage']['mean'] - bundle_def['leakage_advantage']['mean'], 4),
        }

    return {
        'trace_level': {
            'raw': trace_raw,
            'defended': trace_def,
            'defense_gain': round(trace_raw['leakage_advantage']['mean'] - trace_def['leakage_advantage']['mean'], 4),
        },
        'bundle_level': bundle,
    }


def run_significance_analysis(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing_oext/significance')
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / cfg.get('diagnostic_checkpoint_filename', 'summary_significance_checkpoint.json')
    exception_path = output_dir / cfg.get('diagnostic_exception_filename', 'timing_significance_exception.txt')
    permutation_state_path = output_dir / cfg.get('permutation_state_filename', 'timing_significance_permutation_state.json')
    bootstrap_state_path = output_dir / cfg.get('bootstrap_state_filename', 'timing_significance_bootstrap_state.json')
    permutation_output_path = output_dir / cfg.get('permutation_output_filename', 'summary_significance_permutation.json')
    bootstrap_output_path = output_dir / cfg.get('bootstrap_output_filename', 'summary_significance_bootstrap.json')
    progress_log_every = max(1, int(cfg.get('progress_log_every', 50)))
    start_time = time.time()

    print('[timing-significance] starting run_significance_analysis()', flush=True)
    runs, _ = _compute_multiseed(cfg)
    print(f"[timing-significance] multiseed runs ready: {len(runs)} seeds", flush=True)
    bundle_budgets = [int(budget) for budget in cfg.get('probe_budgets_for_significance', cfg.get('probe_budgets', [1, 5, 10, 20, 50, 220]))]
    prepared_trace = _prepare_seed_trace_groups(runs)
    prepared_bundle = _prepare_seed_bundle_groups(runs, cfg, bundle_budgets)
    observed = _significance_views_from_prepared(
        _relabel_seed_trace_groups(prepared_trace),
        _relabel_seed_bundle_groups(prepared_bundle),
        cfg,
    )
    print('[timing-significance] observed statistics computed', flush=True)

    permutation_iterations = int(cfg.get('permutation_iterations', 1000))
    permutation_seed = int(cfg.get('permutation_seed', 0))
    bootstrap_iterations = int(cfg.get('cluster_bootstrap_iterations', 1000))
    bootstrap_seed = int(cfg.get('cluster_bootstrap_seed', 0))
    distribution_template = _blank_significance_distribution(list(observed['bundle_level'].keys()))
    permutation_null, permutation_completed = _load_significance_phase_state(permutation_state_path, distribution_template)
    bootstrap_dist, bootstrap_completed = _load_significance_phase_state(bootstrap_state_path, distribution_template)

    seed_ids = sorted(prepared_trace)
    try:
        print(
            f"[timing-significance] permutation phase: {max(1, permutation_iterations)} iterations "
            f"(resume from {permutation_completed})",
            flush=True,
        )
        for idx in range(permutation_completed, max(1, permutation_iterations)):
            iter_rng = random.Random(permutation_seed + idx)
            swap_flags = {seed_id: iter_rng.random() < 0.5 for seed_id in seed_ids}
            permuted = _significance_views_from_prepared(
                _relabel_seed_trace_groups(prepared_trace, swap_flags=swap_flags),
                _relabel_seed_bundle_groups(prepared_bundle, swap_flags=swap_flags),
                cfg,
            )
            permutation_null['trace_level_raw_leakage_advantage'].append(permuted['trace_level']['raw']['leakage_advantage']['mean'])
            permutation_null['trace_level_defended_leakage_advantage'].append(permuted['trace_level']['defended']['leakage_advantage']['mean'])
            permutation_null['trace_level_defense_gain'].append(permuted['trace_level']['defense_gain'])
            for budget, bundle_view in permuted['bundle_level'].items():
                permutation_null['bundle_level'][budget]['raw_leakage_advantage'].append(bundle_view['raw']['leakage_advantage']['mean'])
                permutation_null['bundle_level'][budget]['defended_leakage_advantage'].append(bundle_view['defended']['leakage_advantage']['mean'])
                permutation_null['bundle_level'][budget]['defense_gain'].append(bundle_view['defense_gain'])

            if (idx + 1) % progress_log_every == 0 or idx == permutation_iterations - 1:
                elapsed = round(time.time() - start_time, 2)
                print(f"[timing-significance] permutation progress {idx + 1}/{permutation_iterations} elapsed={elapsed}s", flush=True)
                _write_significance_checkpoint(checkpoint_path, {
                    'status': 'running',
                    'phase': 'permutation',
                    'completed_iterations': idx + 1,
                    'total_iterations': permutation_iterations,
                    'elapsed_seconds': elapsed,
                })
                _save_significance_phase_state(
                    permutation_state_path,
                    phase='permutation',
                    completed_iterations=idx + 1,
                    total_iterations=permutation_iterations,
                    values=permutation_null,
                    elapsed_seconds=elapsed,
                    status='running',
                )
                permutation_output_path.write_text(
                    json.dumps(
                        _significance_phase_output(
                            observed,
                            permutation_null,
                            phase_name='permutation',
                            iterations=idx + 1,
                            seed=permutation_seed,
                            mode='permutation',
                        ),
                        indent=2,
                    ),
                    encoding='utf-8',
                )

        _save_significance_phase_state(
            permutation_state_path,
            phase='permutation',
            completed_iterations=permutation_iterations,
            total_iterations=permutation_iterations,
            values=permutation_null,
            elapsed_seconds=time.time() - start_time,
            status='completed',
        )
        permutation_output_path.write_text(
            json.dumps(
                _significance_phase_output(
                    observed,
                    permutation_null,
                    phase_name='permutation',
                    iterations=permutation_iterations,
                    seed=permutation_seed,
                    mode='permutation',
                ),
                indent=2,
            ),
            encoding='utf-8',
        )

        print(
            f"[timing-significance] bootstrap phase: {max(1, bootstrap_iterations)} iterations "
            f"(resume from {bootstrap_completed})",
            flush=True,
        )
        for idx in range(bootstrap_completed, max(1, bootstrap_iterations)):
            iter_rng = random.Random(bootstrap_seed + idx)
            sampled_seed_order = [seed_ids[iter_rng.randrange(len(seed_ids))] for _ in range(len(seed_ids))]
            boot = _significance_views_from_prepared(
                _relabel_seed_trace_groups(prepared_trace, sampled_seed_order=sampled_seed_order),
                _relabel_seed_bundle_groups(prepared_bundle, sampled_seed_order=sampled_seed_order),
                cfg,
            )
            bootstrap_dist['trace_level_raw_leakage_advantage'].append(boot['trace_level']['raw']['leakage_advantage']['mean'])
            bootstrap_dist['trace_level_defended_leakage_advantage'].append(boot['trace_level']['defended']['leakage_advantage']['mean'])
            bootstrap_dist['trace_level_defense_gain'].append(boot['trace_level']['defense_gain'])
            for budget, bundle_view in boot['bundle_level'].items():
                bootstrap_dist['bundle_level'][budget]['raw_leakage_advantage'].append(bundle_view['raw']['leakage_advantage']['mean'])
                bootstrap_dist['bundle_level'][budget]['defended_leakage_advantage'].append(bundle_view['defended']['leakage_advantage']['mean'])
                bootstrap_dist['bundle_level'][budget]['defense_gain'].append(bundle_view['defense_gain'])

            if (idx + 1) % progress_log_every == 0 or idx == bootstrap_iterations - 1:
                elapsed = round(time.time() - start_time, 2)
                print(f"[timing-significance] bootstrap progress {idx + 1}/{bootstrap_iterations} elapsed={elapsed}s", flush=True)
                _write_significance_checkpoint(checkpoint_path, {
                    'status': 'running',
                    'phase': 'bootstrap',
                    'completed_iterations': idx + 1,
                    'total_iterations': bootstrap_iterations,
                    'elapsed_seconds': elapsed,
                })
                _save_significance_phase_state(
                    bootstrap_state_path,
                    phase='bootstrap',
                    completed_iterations=idx + 1,
                    total_iterations=bootstrap_iterations,
                    values=bootstrap_dist,
                    elapsed_seconds=elapsed,
                    status='running',
                )
                bootstrap_output_path.write_text(
                    json.dumps(
                        _significance_phase_output(
                            observed,
                            bootstrap_dist,
                            phase_name='bootstrap',
                            iterations=idx + 1,
                            seed=bootstrap_seed,
                            mode='bootstrap',
                        ),
                        indent=2,
                    ),
                    encoding='utf-8',
                )
        _save_significance_phase_state(
            bootstrap_state_path,
            phase='bootstrap',
            completed_iterations=bootstrap_iterations,
            total_iterations=bootstrap_iterations,
            values=bootstrap_dist,
            elapsed_seconds=time.time() - start_time,
            status='completed',
        )
        bootstrap_output_path.write_text(
            json.dumps(
                _significance_phase_output(
                    observed,
                    bootstrap_dist,
                    phase_name='bootstrap',
                    iterations=bootstrap_iterations,
                    seed=bootstrap_seed,
                    mode='bootstrap',
                ),
                indent=2,
            ),
            encoding='utf-8',
        )
    except Exception:
        exception_path.write_text(traceback.format_exc(), encoding='utf-8')
        print(f"[timing-significance] exception captured at {exception_path}", flush=True)
        raise

    output = {
        'scenario': cfg.get('scenario', 'timing_significance'),
        'evaluation_protocol': {
            'split_mode': cfg.get('evaluation_split_mode', 'leave_one_seed_out'),
            'observation_space': cfg.get('observation_space', 'O_ext'),
            'public_feature_set': cfg.get('public_feature_set', 'wait_only'),
            'attacker_secret_unit': 'seed for trace-level grouped LOSO; one held-out victim-family seed for bundle-level proxy',
        },
        'observed': observed,
        'permutation': _significance_phase_output(
            observed,
            permutation_null,
            phase_name='permutation',
            iterations=permutation_iterations,
            seed=permutation_seed,
            mode='permutation',
        ),
        'cluster_bootstrap': _significance_phase_output(
            observed,
            bootstrap_dist,
            phase_name='bootstrap',
            iterations=bootstrap_iterations,
            seed=bootstrap_seed,
            mode='bootstrap',
        ),
    }

    summary_name = cfg.get('output_summary_filename', 'summary_significance.json')
    (output_dir / summary_name).write_text(json.dumps(output, indent=2), encoding='utf-8')
    _write_significance_checkpoint(checkpoint_path, {
        'status': 'completed',
        'phase': 'finished',
        'elapsed_seconds': round(time.time() - start_time, 2),
        'summary_file': summary_name,
    })
    print(f"[timing-significance] completed in {round(time.time() - start_time, 2)}s", flush=True)
    return output


def _defense_profile(variant: str) -> tuple[str, dict]:
    base = {
        'padding': True,
        'mask_backend': True,
        'reset_queue': True,
        'suppress_score': True,
        'cover_target': 0.45,
        'cover_noise': 0.18,
        'release_rule': 'legacy_cover',
        'bucket_width': 0.2,
        'release_noise': 0.0,
        'apply_scope': 'probe_only',
    }
    if variant == 'hardened':
        return 'hardened', dict(base)
    if variant == 'monotone_padding':
        profile = dict(base)
        profile.update({
            'release_rule': 'monotone_padding',
            'cover_target': 0.55,
            'release_noise': 0.03,
            'apply_scope': 'all',
        })
        return 'hardened', profile
    if variant == 'delayed_release':
        profile = dict(base)
        profile.update({
            'release_rule': 'delayed_release',
            'bucket_width': 0.2,
            'release_noise': 0.02,
            'apply_scope': 'all',
        })
        return 'hardened', profile
    if variant == 'hardened_no_padding':
        profile = dict(base)
        profile['padding'] = False
        return 'hardened', profile
    if variant == 'hardened_no_mask':
        profile = dict(base)
        profile['mask_backend'] = False
        return 'hardened', profile
    if variant == 'hardened_no_queue_reset':
        profile = dict(base)
        profile['reset_queue'] = False
        return 'hardened', profile
    if variant == 'hardened_no_score_suppression':
        profile = dict(base)
        profile['suppress_score'] = False
        return 'hardened', profile
    return variant, {}


def _default_quantum_ablation_defaults() -> dict:
    return {
        'use_backend_quality_variation': True,
        'use_queue_time_variation': True,
        'use_backend_utilization_variation': True,
        'use_backend_size_heterogeneity': True,
        'use_compile_path_variation': True,
        'use_noise_shaping_variation': True,
        'use_eligibility_variation': True,
        'use_class_dependent_pressure': True,
        'use_isolation_pressure_boost': True,
        'use_probe_pressure_discount': True,
        'scheduler_override': None,
        'defense_scheduler_override': None,
        'observability_mode_override': None,
        'feature_mode_override': None,
        'compile_config_override': None,
    }


def _resolve_quantum_ablation_profile(name: str, cfg: dict) -> dict:
    profile = _default_quantum_ablation_defaults()
    profile.update(cfg.get('quantum_ablation_defaults', {}))
    profile['compile_config'] = resolve_compile_config(cfg.get('compile_config'))
    profile['ablation_name'] = name
    if name == 'main_quantum':
        return profile
    if name == 'compile_visible':
        profile['feature_mode_override'] = 'compile_visible'
        return profile
    if name == 'logical_only':
        profile['feature_mode_override'] = 'logical_only'
        return profile
    if name == 'uniform_backend_quality':
        profile['use_backend_quality_variation'] = False
        return profile
    if name == 'no_calibration_drift':
        profile['use_queue_time_variation'] = False
        profile['use_backend_utilization_variation'] = False
        return profile
    if name == 'topology_insensitive':
        profile['use_backend_size_heterogeneity'] = False
        profile['use_eligibility_variation'] = False
        return profile
    if name == 'compile_path_neutralized':
        profile['use_compile_path_variation'] = False
        profile['use_eligibility_variation'] = False
        return profile
    if name == 'shuffled_compile_features':
        profile['feature_mode_override'] = 'shuffled_compile'
        return profile
    if name == 'random_matched_features':
        profile['feature_mode_override'] = 'random_matched'
        return profile
    if name == 'noise_flattened':
        profile['use_noise_shaping_variation'] = False
        return profile
    if name == 'no_coexecution_sensitivity':
        profile['use_isolation_pressure_boost'] = False
        profile['use_class_dependent_pressure'] = False
        return profile
    if name == 'classical_queue_baseline':
        profile['use_backend_quality_variation'] = False
        profile['use_class_dependent_pressure'] = False
        profile['use_isolation_pressure_boost'] = False
        profile['scheduler_override'] = 'queue'
        return profile
    if name == 'coarse_observability_baseline':
        profile['observability_mode_override'] = 'coarse'
        return profile
    if name == 'masked_backend_only_baseline':
        profile['observability_mode_override'] = 'masked_backend_only'
        return profile
    if name == 'queue_length_only_baseline':
        profile['observability_mode_override'] = 'queue_length_only'
        return profile
    raise ValueError(f'unknown quantum ablation profile: {name}')


def _resolve_noise_heterogeneity_profile(name: str, cfg: dict) -> dict:
    profile = _default_quantum_ablation_defaults()
    profile.update(cfg.get('quantum_ablation_defaults', {}))
    profile['compile_config'] = resolve_compile_config(cfg.get('compile_config'))
    profile['ablation_name'] = name
    if name == 'uniform_noise':
        profile['noise_profile_mode'] = 'uniform'
        profile['heterogeneity_intensity'] = 0.25
        return profile
    if name == 'moderate_heterogeneity':
        profile['noise_profile_mode'] = 'moderate'
        profile['heterogeneity_intensity'] = 0.7
        return profile
    if name == 'high_drift':
        profile['noise_profile_mode'] = 'high_drift'
        profile['heterogeneity_intensity'] = 1.0
        return profile
    raise ValueError(f'unknown noise heterogeneity profile: {name}')


def _compute_job_pressure(job, pressure_profile: dict) -> float:
    pressure = 0.015 * max(job.depth(), 1)
    if pressure_profile.get('use_isolation_pressure_boost', True) and job.metadata.isolation_level == 'high':
        pressure += 0.65
    if pressure_profile.get('use_class_dependent_pressure', True):
        if 'pressure_bias' in job.metadata.notes:
            pressure += float(job.metadata.notes.get('pressure_bias', 0.0))
        elif job.metadata.workload_tag == 'classB':
            pressure += 0.55
        elif job.metadata.workload_tag == 'classA':
            pressure += 0.08
    if pressure_profile.get('use_probe_pressure_discount', True) and job.metadata.workload_tag == 'probe':
        pressure *= 0.25
    pressure *= pressure_profile.get('pressure_multiplier', 1.0)
    return pressure


def _annotate_job_quantum_proxies(job, label: str, backends: list, pressure_profile: dict) -> None:
    depth = int(job.depth())
    num_qubits = int(job.num_qubits())
    job.logical_qubits = num_qubits
    job.depth_proxy = float(depth)
    backend_ids = [backend.backend_id for backend in backends]
    compile_enabled = annotate_job_compile_features(
        job,
        label,
        backends,
        use_compile_path_variation=pressure_profile.get('use_compile_path_variation', True),
        use_eligibility_variation=pressure_profile.get('use_eligibility_variation', True),
        compile_config=pressure_profile.get('compile_config_override') or pressure_profile.get('compile_config'),
    )
    if compile_enabled:
        return
    base_two_qubit = max(6, depth // 4)
    compile_base = 0.015 * depth + 0.04 * num_qubits + 0.003 * base_two_qubit

    if pressure_profile.get('use_compile_path_variation', True):
        if label == 'classB':
            compile_scale = 1.35
        elif label == 'highIsolation':
            compile_scale = 1.2
        elif label == 'classA':
            compile_scale = 1.0
        else:
            compile_scale = 0.9
        isolation_penalty = 0.18 if job.metadata.isolation_level == 'high' else 0.0
        job.estimated_compile_cost = round(compile_base * compile_scale + isolation_penalty, 4)
        job.two_qubit_gate_proxy = float(base_two_qubit * compile_scale)
        if pressure_profile.get('use_eligibility_variation', True):
            if label == 'classB':
                job.backend_eligibility = backend_ids[: max(1, len(backend_ids) - 1)]
            elif label == 'highIsolation':
                job.backend_eligibility = backend_ids[-max(1, len(backend_ids) - 1):]
            else:
                job.backend_eligibility = list(backend_ids)
        else:
            job.backend_eligibility = list(backend_ids)
    else:
        job.estimated_compile_cost = round(0.012 * depth + 0.03 * num_qubits, 4)
        job.two_qubit_gate_proxy = float(max(6, depth // 5))
        job.backend_eligibility = list(backend_ids)


def _build_probe_scenario(seed: int, label: str, cfg: dict, quantum_ablation: dict | None = None) -> dict:
    rng = random.Random(seed)
    workload_profile = _resolve_workload_profile(cfg)
    benign_base = int(round(cfg['benign_jobs'] * workload_profile.get('benign_count_scale', 1.0)))
    probe_base = int(round(cfg['probe_jobs'] * workload_profile.get('probe_count_scale', 1.0)))
    victim_base = int(round(cfg['victim_jobs'] * workload_profile.get('victim_count_scale', 1.0)))
    benign_count = max(1, benign_base + rng.randint(0, 6))
    probe_count = max(int(cfg.get('min_probe_jobs', 8)), probe_base)
    victim_count = max(1, victim_base + rng.randint(0, 4))
    benign_gap = workload_profile.get('benign_arrival_gap', 0.6)
    victim_gap = workload_profile.get('victim_arrival_gap', 0.75)
    probe_gap = workload_profile.get('probe_arrival_gap', 0.55)
    benign_jitter = workload_profile.get('benign_jitter', 0.15)
    probe_jitter = workload_profile.get('probe_jitter', 0.06)
    probe_start = workload_profile.get('probe_start', 1.0)
    probe_phase_stride = max(1, int(workload_profile.get('probe_phase_stride', 22)))
    benign_burst_every = max(0, int(workload_profile.get('benign_burst_every', 0)))
    benign_burst_extra = workload_profile.get('benign_burst_extra', 0.0)
    tenant_mode = workload_profile.get('tenant_mode', 'stable')
    benign_tenant_pool = max(1, int(workload_profile.get('benign_tenant_pool', 2)))
    tenant_drift_stride = max(1, int(workload_profile.get('tenant_drift_stride', 6)))
    mixed_sensitive_ratio = max(0.0, min(1.0, float(workload_profile.get('mixed_sensitive_ratio', 0.0))))
    mixed_heavy_ratio = max(0.0, min(1.0, float(workload_profile.get('mixed_heavy_ratio', 0.0))))

    benign_jobs = []
    for i in range(benign_count):
        submit = i * benign_gap + rng.uniform(-benign_jitter, benign_jitter)
        if benign_burst_every and i and i % benign_burst_every == 0:
            submit -= benign_burst_extra
        if tenant_mode == 'drifting':
            tenant_idx = (i // tenant_drift_stride) % benign_tenant_pool
            tenant_id = f'tenant{tenant_idx}'
            submit += 0.05 * tenant_idx
            depth_bias = workload_profile.get('benign_depth_bias', 0) + 6 * tenant_idx
        elif tenant_mode == 'mixed_sensitivity_pressure':
            tenant_idx = i % max(3, benign_tenant_pool)
            tenant_id = f'tenant{tenant_idx}'
            depth_bias = workload_profile.get('benign_depth_bias', 0) + (12 if tenant_idx == 1 else 0) + (20 if tenant_idx == 2 else 0)
        else:
            tenant_id = f'tenant{i % benign_tenant_pool}'
            depth_bias = workload_profile.get('benign_depth_bias', 0)
        job = synthetic_job(
            f'benign-{i}',
            tenant_id,
            float(max(0.0, submit)),
            4 + (i % 4),
            35 + depth_bias + (i % 4) * 12 + rng.randint(-6, 8),
            workload_tag='benign',
        )
        job.workload_role = 'benign'
        job.sensitivity = 'normal'
        if tenant_mode == 'mixed_sensitivity_pressure':
            if i < int(round(benign_count * mixed_sensitive_ratio)):
                job.sensitivity = 'sensitive'
                job.metadata.isolation_level = 'high'
            if i >= benign_count - int(round(benign_count * mixed_heavy_ratio)):
                job.workload_role = 'heavy'
                job.metadata.notes['depth'] = int(job.metadata.notes['depth']) + 24
        benign_jobs.append(job)
    victim_jobs = _build_victim_jobs(label, victim_count, rng, cfg)
    for i, job in enumerate(victim_jobs):
        shifted = workload_profile.get('victim_start', 1.0) + i * victim_gap + rng.uniform(-workload_profile.get('victim_jitter', 0.12), workload_profile.get('victim_jitter', 0.12))
        job.submit_time = float(max(0.0, shifted))
        job.metadata.notes['depth'] = max(1, job.depth() + workload_profile.get('victim_depth_bias', 0))
    probe_jobs = [
        build_probe_job(
            f'probe-{i}',
            float(max(0.0, probe_start + (i % probe_phase_stride) * probe_gap + rng.uniform(-probe_jitter, probe_jitter))),
            num_qubits=2 + (i % 2),
            depth=max(2, 8 + workload_profile.get('probe_depth_bias', 0) + rng.randint(-2, 3)),
        )
        for i in range(probe_count)
    ]
    ordered = benign_jobs[: len(benign_jobs)//2] + victim_jobs + probe_jobs + benign_jobs[len(benign_jobs)//2 :]
    ordered.sort(key=lambda j: j.submit_time)
    ablation = quantum_ablation or _resolve_quantum_ablation_profile('main_quantum', cfg)
    backend_profile = {
        'use_backend_quality_variation': ablation.get('use_backend_quality_variation', True),
        'use_queue_time_variation': ablation.get('use_queue_time_variation', True),
        'use_backend_utilization_variation': ablation.get('use_backend_utilization_variation', True),
        'use_backend_size_heterogeneity': ablation.get('use_backend_size_heterogeneity', True),
        'use_compile_path_variation': ablation.get('use_compile_path_variation', True),
        'use_noise_shaping_variation': ablation.get('use_noise_shaping_variation', True),
        'noise_profile_mode': ablation.get('noise_profile_mode', cfg.get('noise_profile_mode', 'default')),
        'heterogeneity_intensity': ablation.get('heterogeneity_intensity', cfg.get('heterogeneity_intensity', 1.0)),
    }
    pressure_profile = {
        'use_class_dependent_pressure': ablation.get('use_class_dependent_pressure', True),
        'use_isolation_pressure_boost': ablation.get('use_isolation_pressure_boost', True),
        'use_probe_pressure_discount': ablation.get('use_probe_pressure_discount', True),
        'pressure_multiplier': workload_profile.get('pressure_multiplier', 1.0),
    }
    pressures = {}
    for job in ordered:
        pressures[job.job_id] = _compute_job_pressure(job, pressure_profile)
    backends = clone_backends(rng, backend_profile=backend_profile)
    for job in ordered:
        _annotate_job_quantum_proxies(job, label, backends, ablation)
    return {
        'jobs': ordered,
        'pressures': pressures,
        'backends': backends,
        'scenario_meta': {
            'ablation_name': ablation.get('ablation_name', 'main_quantum'),
            'backend_profile': backend_profile,
            'pressure_profile': pressure_profile,
            'workload_profile': workload_profile,
            'compile_path_variation': ablation.get('use_compile_path_variation', True),
            'noise_shaping_variation': ablation.get('use_noise_shaping_variation', True),
            'eligibility_variation': ablation.get('use_eligibility_variation', True),
        },
    }


def _run_probe_scenario(scenario: dict, scheduler_name: str, observability_mode: str, defense_profile: dict | None = None, scenario_meta: dict | None = None) -> dict:
    env = SimulationEnvironment(
        backends=copy.deepcopy(scenario['backends']),
        scheduler=build_scheduler(scheduler_name),
        rng=random.Random(0),
        observability_mode=observability_mode,
        defense_profile=defense_profile or {},
    )
    probe_traces = []
    tenant_waits = {}
    sensitive_waits = []
    victim_waits = []
    victim_qualities = []
    release_records = []
    for job in copy.deepcopy(scenario['jobs']):
        pressure = scenario['pressures'][job.job_id]
        record = env.step(job, pressure=pressure)
        tenant_waits.setdefault(job.tenant_id, []).append(float(record.estimated_wait))
        if job.sensitivity == 'sensitive':
            sensitive_waits.append(float(record.estimated_wait))
        if job.tenant_id == 'victim':
            victim_waits.append(float(record.estimated_wait))
            victim_qualities.append(float(record.estimated_quality))
        observed_wait = float(record.observed.get('observed_wait', record.estimated_wait))
        release_records.append({
            'job_id': record.job_id,
            'tenant_id': record.tenant_id,
            'workload_tag': job.metadata.workload_tag,
            'submit_time': float(job.submit_time),
            'estimated_wait': float(record.estimated_wait),
            'observed_wait': observed_wait,
            'release_time': float(job.submit_time) + observed_wait,
            'accepted': bool(record.accepted),
        })
        if job.metadata.workload_tag == 'probe':
            observed = dict(record.observed)
            observed['public_status'] = 1.0 if record.accepted else 0.0
            observed['logical_qubits'] = float(getattr(job, 'logical_qubits', 0.0) or 0.0)
            observed['logical_depth'] = float(getattr(job, 'depth_proxy', 0.0) or 0.0)
            probe_traces.append(observed)
    tenant_means = [sum(waits) / len(waits) for waits in tenant_waits.values() if waits]
    waits = [x.get('observed_wait', 0.0) for x in probe_traces]
    backend_labels = [str(x.get('backend_id', 'masked')) for x in probe_traces]
    score_margins = [float(x.get('score_margin', 0.0)) for x in probe_traces]
    accepted_records = [record for record in release_records if record['accepted']]
    accepted_waits = [record['observed_wait'] for record in accepted_records]
    release_times = [record['release_time'] for record in accepted_records]
    submit_times = [record['submit_time'] for record in accepted_records]
    release_makespan = (max(release_times) - min(submit_times)) if release_times and submit_times else 0.0
    backend_utilizations = [
        float(snapshot['utilization'])
        for history in env.backend_history
        for snapshot in history.get('snapshots', [])
    ]
    return {
        'probe_count': len(probe_traces),
        'probe_mean_wait': round(mean(waits), 4) if waits else 0.0,
        'probe_std_wait': round(pstdev(waits), 4) if len(waits) > 1 else 0.0,
        'backend_choice_entropy': round(_entropy(backend_labels), 4),
        'score_margin_variance': round(_variance(score_margins), 4),
        'tenant_wait_dispersion': round((max(tenant_means) - min(tenant_means)) if tenant_means else 0.0, 4),
        'tenant_wait_fairness': round(_fairness_index(tenant_means), 4) if tenant_means else 0.0,
        'sensitive_mean_wait_proxy': round(mean(sensitive_waits), 4) if sensitive_waits else 0.0,
        'victim_mean_wait': round(mean(victim_waits), 4) if victim_waits else 0.0,
        'victim_mean_quality': round(mean(victim_qualities), 4) if victim_qualities else 0.0,
        'release_mean_wait_all': round(mean(accepted_waits), 4) if accepted_waits else 0.0,
        'release_p95_wait_all': round(_percentile(accepted_waits, 0.95), 4) if accepted_waits else 0.0,
        'release_throughput_all': round((len(accepted_records) / release_makespan), 4) if release_makespan > 0 else 0.0,
        'avg_backend_utilization': round(mean(backend_utilizations), 4) if backend_utilizations else 0.0,
        'release_records': release_records,
        'probe_traces': probe_traces,
        'scheduler_used': scheduler_name,
        'observability_mode_used': observability_mode,
        'scenario_meta': scenario_meta or scenario.get('scenario_meta', {}),
    }


def _compile_feature_tuple(item: dict) -> tuple[float, float, float, float, float, float]:
    return (
        float(item.get('compiled_depth', 0.0)),
        float(item.get('cx_count', 0.0)),
        float(item.get('swap_count', 0.0)),
        float(item.get('layout_span', 0.0)),
        float(item.get('expected_fidelity', 0.0)),
        float(item.get('backend_suitability', 0.0)),
    )


def _prepare_feature_mode_traces(scenarios: dict[str, dict], seed: int, feature_mode: str) -> None:
    if feature_mode not in {'shuffled_compile', 'random_matched'}:
        return

    trace_groups = []
    for name in ['classA', 'classB', 'highIsolation', 'noVictim', 'classA_defended', 'classB_defended']:
        if name in scenarios:
            trace_groups.append(scenarios[name]['probe_traces'])
    traces = [trace for group in trace_groups for trace in group]
    if not traces:
        return

    if feature_mode == 'shuffled_compile':
        rng = random.Random(seed * 97 + 11)
        shuffled = [_compile_feature_tuple(trace) for trace in traces]
        rng.shuffle(shuffled)
        for trace, values in zip(traces, shuffled):
            (
                trace['shuffled_compiled_depth'],
                trace['shuffled_cx_count'],
                trace['shuffled_swap_count'],
                trace['shuffled_layout_span'],
                trace['shuffled_expected_fidelity'],
                trace['shuffled_backend_suitability'],
            ) = values
        return

    if feature_mode == 'random_matched':
        rng = random.Random(seed * 101 + 17)
        dims = list(zip(*[_compile_feature_tuple(trace) for trace in traces]))
        means = [sum(dim) / len(dim) for dim in dims]
        stds = []
        for dim, mu in zip(dims, means):
            var = sum((value - mu) ** 2 for value in dim) / len(dim)
            stds.append(var ** 0.5 if var > 1e-9 else 1.0)
        for trace in traces:
            sampled = [rng.gauss(mu, sigma) for mu, sigma in zip(means, stds)]
            (
                trace['random_compiled_depth'],
                trace['random_cx_count'],
                trace['random_swap_count'],
                trace['random_layout_span'],
                trace['random_expected_fidelity'],
                trace['random_backend_suitability'],
            ) = sampled


def _compare_attack_and_defense(
    seed: int,
    cfg: dict,
    defense_mode: str,
    defense_profile: dict | None = None,
    quantum_ablation: dict | None = None,
    feature_mode: str = 'base',
) -> dict:
    ablation = quantum_ablation or _resolve_quantum_ablation_profile('main_quantum', cfg)
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    observation_space = cfg.get('observation_space', 'O_sb')
    public_feature_set = cfg.get('public_feature_set', 'wait_backend')
    attack_scheduler = ablation.get('scheduler_override') or cfg.get('attack_scheduler') or cfg['baseline_names'][0]
    defense_scheduler = ablation.get('defense_scheduler_override') or cfg.get('defense_scheduler') or ('secure_joint' if 'secure_joint' in cfg['baseline_names'] else cfg['baseline_names'][0])
    full_mode = ablation.get('observability_mode_override') or cfg.get('observability_mode') or _observation_mode_from_space(observation_space)
    base_scenarios = {
        'classA': _build_probe_scenario(seed * 13 + 1, 'classA', cfg, ablation),
        'classB': _build_probe_scenario(seed * 13 + 2, 'classB', cfg, ablation),
        'highIsolation': _build_probe_scenario(seed * 13 + 3, 'highIsolation', cfg, ablation),
        'noVictim': _build_probe_scenario(seed * 13 + 4, 'none', cfg, ablation),
    }
    scenarios = {
        'classA': _run_probe_scenario(base_scenarios['classA'], attack_scheduler, full_mode, scenario_meta=base_scenarios['classA'].get('scenario_meta')),
        'classB': _run_probe_scenario(base_scenarios['classB'], attack_scheduler, full_mode, scenario_meta=base_scenarios['classB'].get('scenario_meta')),
        'highIsolation': _run_probe_scenario(base_scenarios['highIsolation'], attack_scheduler, full_mode, scenario_meta=base_scenarios['highIsolation'].get('scenario_meta')),
        'noVictim': _run_probe_scenario(base_scenarios['noVictim'], attack_scheduler, full_mode, scenario_meta=base_scenarios['noVictim'].get('scenario_meta')),
        'classA_defended': _run_probe_scenario(base_scenarios['classA'], defense_scheduler, defense_mode, defense_profile, base_scenarios['classA'].get('scenario_meta')),
        'classB_defended': _run_probe_scenario(base_scenarios['classB'], defense_scheduler, defense_mode, defense_profile, base_scenarios['classB'].get('scenario_meta')),
    }
    _prepare_feature_mode_traces(scenarios, seed, feature_mode)
    clf = _linear_classifier(
        scenarios['classA']['probe_traces'],
        scenarios['classB']['probe_traces'],
        seed * 17 + 1,
        feature_mode=feature_mode,
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        public_feature_set=public_feature_set,
    )
    clf_def = _linear_classifier(
        scenarios['classA_defended']['probe_traces'],
        scenarios['classB_defended']['probe_traces'],
        seed * 17 + 2,
        feature_mode=feature_mode,
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        public_feature_set=public_feature_set,
    )
    backend_clf = _linear_classifier(
        scenarios['classA']['probe_traces'],
        scenarios['classB']['probe_traces'],
        seed * 17 + 5,
        feature_mode='backend_only',
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        public_feature_set=public_feature_set,
    )
    thr = _threshold_classifier(scenarios['classA']['probe_traces'], scenarios['classB']['probe_traces'], seed * 17 + 3)
    thr_def = _threshold_classifier(scenarios['classA_defended']['probe_traces'], scenarios['classB_defended']['probe_traces'], seed * 17 + 4)
    defense_gain = round(clf['leakage_advantage'] - clf_def['leakage_advantage'], 4)
    return {
        'seed': seed,
        'ablation_name': ablation.get('ablation_name', 'main_quantum'),
        'defense_mode': defense_mode,
        'scheduler_used_raw': attack_scheduler,
        'scheduler_used_defended': defense_scheduler,
        'observability_mode_raw': full_mode,
        'observability_mode_defended': defense_mode,
        'observation_space': observation_space,
        'backend_encoding': backend_encoding,
        'public_feature_set': public_feature_set,
        'backend_profile_flags': base_scenarios['classA']['scenario_meta']['backend_profile'],
        'pressure_profile_flags': base_scenarios['classA']['scenario_meta']['pressure_profile'],
        'classA_mean_wait': scenarios['classA']['probe_mean_wait'],
        'classB_mean_wait': scenarios['classB']['probe_mean_wait'],
        'highIsolation_mean_wait': scenarios['highIsolation']['probe_mean_wait'],
        'noVictim_mean_wait': scenarios['noVictim']['probe_mean_wait'],
        'class_gap': round(scenarios['classB']['probe_mean_wait'] - scenarios['classA']['probe_mean_wait'], 4),
        'highIsolation_delta_from_classA': round(scenarios['highIsolation']['probe_mean_wait'] - scenarios['classA']['probe_mean_wait'], 4),
        'classA_minus_noVictim': round(scenarios['classA']['probe_mean_wait'] - scenarios['noVictim']['probe_mean_wait'], 4),
        'classB_minus_noVictim': round(scenarios['classB']['probe_mean_wait'] - scenarios['noVictim']['probe_mean_wait'], 4),
        'highIsolation_minus_noVictim': round(scenarios['highIsolation']['probe_mean_wait'] - scenarios['noVictim']['probe_mean_wait'], 4),
        'accuracy': clf['accuracy'],
        'leakage_advantage': clf['leakage_advantage'],
        'backend_choice_accuracy': backend_clf['accuracy'],
        'backend_choice_leakage_advantage': backend_clf['leakage_advantage'],
        'threshold_accuracy': thr['threshold_accuracy'],
        'threshold_leakage_advantage': thr['threshold_leakage_advantage'],
        'defended_accuracy': clf_def['accuracy'],
        'defended_leakage_advantage': clf_def['leakage_advantage'],
        'defended_threshold_accuracy': thr_def['threshold_accuracy'],
        'defended_threshold_leakage_advantage': thr_def['threshold_leakage_advantage'],
        'defense_gain': defense_gain,
        'tenant_wait_dispersion_raw': scenarios['classB']['tenant_wait_dispersion'],
        'tenant_wait_fairness_raw': scenarios['classB']['tenant_wait_fairness'],
        'tenant_wait_dispersion_defended': scenarios['classB_defended']['tenant_wait_dispersion'],
        'tenant_wait_fairness_defended': scenarios['classB_defended']['tenant_wait_fairness'],
        'sensitive_mean_wait_proxy_raw': scenarios['classB']['sensitive_mean_wait_proxy'],
        'sensitive_mean_wait_proxy_defended': scenarios['classB_defended']['sensitive_mean_wait_proxy'],
        'scenarios': scenarios,
    }


def _pair_release_records(raw_records: list[dict], defended_records: list[dict]) -> list[dict]:
    defended_by_job = {str(item['job_id']): item for item in defended_records}
    paired = []
    for raw in raw_records:
        defended = defended_by_job.get(str(raw['job_id']))
        if defended is None:
            continue
        paired.append({
            'job_id': str(raw['job_id']),
            'tenant_id': str(raw.get('tenant_id', 'unknown')),
            'workload_tag': str(raw.get('workload_tag', 'unknown')),
            'raw_wait': float(raw.get('observed_wait', 0.0)),
            'defended_wait': float(defended.get('observed_wait', 0.0)),
            'extra_wait': float(defended.get('observed_wait', 0.0)) - float(raw.get('observed_wait', 0.0)),
            'raw_release_time': float(raw.get('release_time', 0.0)),
            'defended_release_time': float(defended.get('release_time', 0.0)),
        })
    return paired


def _release_utility_from_pairs(raw_scenario: dict, defended_scenario: dict) -> dict:
    paired = _pair_release_records(raw_scenario.get('release_records', []), defended_scenario.get('release_records', []))
    extra_waits = [max(0.0, float(item['extra_wait'])) for item in paired]
    raw_release_times = [float(item.get('release_time', 0.0)) for item in raw_scenario.get('release_records', []) if item.get('accepted', True)]
    raw_submit_times = [float(item.get('submit_time', 0.0)) for item in raw_scenario.get('release_records', []) if item.get('accepted', True)]
    def_release_times = [float(item.get('defended_release_time', item.get('release_time', 0.0))) for item in paired]
    def_submit_times = [float(item.get('submit_time', 0.0)) for item in defended_scenario.get('release_records', []) if item.get('accepted', True)]
    raw_makespan = (max(raw_release_times) - min(raw_submit_times)) if raw_release_times and raw_submit_times else 0.0
    def_makespan = (max(def_release_times) - min(def_submit_times)) if def_release_times and def_submit_times else 0.0
    raw_throughput = (len(raw_release_times) / raw_makespan) if raw_makespan > 0 else 0.0
    def_throughput = (len(def_release_times) / def_makespan) if def_makespan > 0 else 0.0
    return {
        'mean_extra_wait': round(mean(extra_waits), 4) if extra_waits else 0.0,
        'p95_extra_wait': round(_percentile(extra_waits, 0.95), 4) if extra_waits else 0.0,
        'visible_throughput_raw': round(raw_throughput, 4),
        'visible_throughput_defended': round(def_throughput, 4),
        'visible_throughput_delta': round(def_throughput - raw_throughput, 4),
        'avg_backend_utilization_raw': float(raw_scenario.get('avg_backend_utilization', 0.0)),
        'avg_backend_utilization_defended': float(defended_scenario.get('avg_backend_utilization', 0.0)),
        'avg_backend_utilization_delta': round(
            float(defended_scenario.get('avg_backend_utilization', 0.0)) - float(raw_scenario.get('avg_backend_utilization', 0.0)),
            4,
        ),
    }


def _run_release_variant(seed: int, cfg: dict, variant: str) -> dict:
    defense_scheduler = cfg.get('defense_scheduler') or ('secure_joint' if 'secure_joint' in cfg['baseline_names'] else cfg['baseline_names'][0])
    observation_space = cfg.get('observation_space', 'O_ext')
    public_feature_set = cfg.get('public_feature_set', 'wait_only')
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    full_mode = cfg.get('observability_mode') or _observation_mode_from_space(observation_space)
    base_scenarios = {
        'classA': _build_probe_scenario(seed * 13 + 1, 'classA', cfg),
        'classB': _build_probe_scenario(seed * 13 + 2, 'classB', cfg),
    }
    baseline = {
        'classA': _run_probe_scenario(base_scenarios['classA'], defense_scheduler, full_mode, scenario_meta=base_scenarios['classA'].get('scenario_meta')),
        'classB': _run_probe_scenario(base_scenarios['classB'], defense_scheduler, full_mode, scenario_meta=base_scenarios['classB'].get('scenario_meta')),
    }
    if variant == 'raw':
        defended = baseline
        defense_mode = full_mode
        defense_profile = {}
    else:
        defense_mode, defense_profile = _defense_profile(variant)
        defended = {
            'classA': _run_probe_scenario(base_scenarios['classA'], defense_scheduler, defense_mode, defense_profile, base_scenarios['classA'].get('scenario_meta')),
            'classB': _run_probe_scenario(base_scenarios['classB'], defense_scheduler, defense_mode, defense_profile, base_scenarios['classB'].get('scenario_meta')),
        }
    clf = _linear_classifier(
        defended['classA']['probe_traces'],
        defended['classB']['probe_traces'],
        seed * 17 + 31,
        observation_space=observation_space,
        backend_encoding=backend_encoding,
        public_feature_set=public_feature_set,
    )
    utility_a = _release_utility_from_pairs(baseline['classA'], defended['classA'])
    utility_b = _release_utility_from_pairs(baseline['classB'], defended['classB'])
    visible_throughput_raw = mean([utility_a['visible_throughput_raw'], utility_b['visible_throughput_raw']])
    visible_throughput_defended = mean([utility_a['visible_throughput_defended'], utility_b['visible_throughput_defended']])
    return {
        'seed': seed,
        'variant': variant,
        'scheduler_used': defense_scheduler,
        'accuracy': clf['accuracy'],
        'leakage_advantage': clf['leakage_advantage'],
        'mean_extra_wait': round(mean([utility_a['mean_extra_wait'], utility_b['mean_extra_wait']]), 4),
        'p95_extra_wait': round(mean([utility_a['p95_extra_wait'], utility_b['p95_extra_wait']]), 4),
        'visible_throughput_raw': round(visible_throughput_raw, 4),
        'visible_throughput_defended': round(visible_throughput_defended, 4),
        'visible_throughput_delta': round(mean([utility_a['visible_throughput_delta'], utility_b['visible_throughput_delta']]), 4),
        'avg_backend_utilization_raw': round(mean([utility_a['avg_backend_utilization_raw'], utility_b['avg_backend_utilization_raw']]), 4),
        'avg_backend_utilization_defended': round(mean([utility_a['avg_backend_utilization_defended'], utility_b['avg_backend_utilization_defended']]), 4),
        'avg_backend_utilization_delta': round(mean([utility_a['avg_backend_utilization_delta'], utility_b['avg_backend_utilization_delta']]), 4),
        'scenarios': defended,
    }


def run_once(seed: int, cfg: dict) -> dict:
    set_seed(seed)
    defense_mode, defense_profile = _defense_profile(cfg.get('masked_mode', 'hardened'))
    return _compare_attack_and_defense(seed, cfg, defense_mode, defense_profile)


def _compute_multiseed(cfg: dict) -> tuple[list[dict], dict]:
    runs = []
    stats_options = _stats_options(cfg)
    metrics = [
        'classA_mean_wait', 'classB_mean_wait', 'highIsolation_mean_wait', 'noVictim_mean_wait',
        'class_gap', 'highIsolation_delta_from_classA', 'classA_minus_noVictim',
        'classB_minus_noVictim', 'highIsolation_minus_noVictim', 'accuracy', 'leakage_advantage',
        'threshold_accuracy', 'threshold_leakage_advantage', 'defended_accuracy',
        'defended_leakage_advantage', 'defended_threshold_accuracy',
        'defended_threshold_leakage_advantage', 'defense_gain',
        'tenant_wait_dispersion_raw', 'tenant_wait_fairness_raw',
        'tenant_wait_dispersion_defended', 'tenant_wait_fairness_defended',
        'sensitive_mean_wait_proxy_raw', 'sensitive_mean_wait_proxy_defended'
    ]
    for seed in cfg['seeds']:
        runs.append(run_once(seed, cfg))
    aggregate = aggregate_metrics(runs, metrics, **stats_options)
    split_mode = cfg.get('evaluation_split_mode', 'trace_holdout')
    if split_mode != 'trace_holdout':
        grouped_raw = _grouped_classifier_summary(
            *_seed_grouped_dataset(runs, 'classA', 'classB'),
            split_mode=split_mode,
            seed=int(cfg.get('grouped_split_seed', 0)),
            feature_mode=cfg.get('feature_mode', 'base'),
            observation_space=cfg.get('observation_space', 'O_sb'),
            backend_encoding=cfg.get('backend_encoding', 'onehot'),
            stats_options=stats_options,
            public_feature_set=cfg.get('public_feature_set', 'wait_backend'),
        )
        grouped_def = _grouped_classifier_summary(
            *_seed_grouped_dataset(runs, 'classA_defended', 'classB_defended'),
            split_mode=split_mode,
            seed=int(cfg.get('grouped_split_seed', 0)),
            feature_mode=cfg.get('feature_mode', 'base'),
            observation_space=cfg.get('observation_space', 'O_sb'),
            backend_encoding=cfg.get('backend_encoding', 'onehot'),
            stats_options=stats_options,
            public_feature_set=cfg.get('public_feature_set', 'wait_backend'),
        )
        grouped_backend = _grouped_classifier_summary(
            *_seed_grouped_dataset(runs, 'classA', 'classB'),
            split_mode=split_mode,
            seed=int(cfg.get('grouped_split_seed', 0)),
            feature_mode='backend_only',
            observation_space=cfg.get('observation_space', 'O_sb'),
            backend_encoding=cfg.get('backend_encoding', 'onehot'),
            stats_options=stats_options,
            public_feature_set=cfg.get('public_feature_set', 'wait_backend'),
        )
        aggregate['metrics']['accuracy'] = grouped_raw['accuracy']
        aggregate['metrics']['leakage_advantage'] = grouped_raw['leakage_advantage']
        aggregate['metrics']['threshold_accuracy'] = grouped_raw['threshold_accuracy']
        aggregate['metrics']['threshold_leakage_advantage'] = grouped_raw['threshold_leakage_advantage']
        aggregate['metrics']['defended_accuracy'] = grouped_def['accuracy']
        aggregate['metrics']['defended_leakage_advantage'] = grouped_def['leakage_advantage']
        aggregate['metrics']['defended_threshold_accuracy'] = grouped_def['threshold_accuracy']
        aggregate['metrics']['defended_threshold_leakage_advantage'] = grouped_def['threshold_leakage_advantage']
        aggregate['metrics']['backend_choice_accuracy'] = grouped_backend['accuracy']
        aggregate['metrics']['backend_choice_leakage_advantage'] = grouped_backend['leakage_advantage']
        aggregate['metrics']['defense_gain'] = summarize(
            [
                grouped_raw['leakage_advantage']['mean'] - grouped_def['leakage_advantage']['mean']
            ],
            **stats_options,
        )
        aggregate['evaluation_protocol'] = {
            'split_mode': split_mode,
            'observation_space': cfg.get('observation_space', 'O_sb'),
            'backend_encoding': cfg.get('backend_encoding', 'onehot'),
            'public_feature_set': cfg.get('public_feature_set', 'wait_backend'),
            'ci_method': stats_options['ci_method'],
        }
    return runs, aggregate


def run_multiseed(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing')
    output_dir.mkdir(parents=True, exist_ok=True)
    runs, aggregate = _compute_multiseed(cfg)
    for run in runs:
        seed_name = cfg.get('output_seed_template', 'summary_seed_{seed}.json').format(seed=run['seed'])
        (output_dir / seed_name).write_text(json.dumps(run, indent=2), encoding='utf-8')
    summary_name = cfg.get('output_summary_filename', 'summary_multiseed.json')
    (output_dir / summary_name).write_text(json.dumps(aggregate, indent=2), encoding='utf-8')
    return aggregate


def run_release_tradeoff(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing_oext/release_tradeoff')
    output_dir.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    variants = cfg.get('release_tradeoff_variants', ['raw', 'monotone_padding', 'delayed_release'])
    metric_names = [
        'accuracy',
        'leakage_advantage',
        'mean_extra_wait',
        'p95_extra_wait',
        'visible_throughput_raw',
        'visible_throughput_defended',
        'visible_throughput_delta',
        'avg_backend_utilization_raw',
        'avg_backend_utilization_defended',
        'avg_backend_utilization_delta',
    ]
    seed_runs: dict[str, list[dict]] = {}
    summaries: dict[str, dict] = {}
    for variant in variants:
        runs = [_run_release_variant(seed, cfg, variant) for seed in cfg['seeds']]
        seed_runs[variant] = runs
        summaries[variant] = aggregate_metrics(runs, metric_names, **stats_options)
        grouped = _grouped_classifier_summary(
            *_seed_grouped_dataset(runs, 'classA', 'classB'),
            split_mode=cfg.get('evaluation_split_mode', 'leave_one_seed_out'),
            seed=int(cfg.get('grouped_split_seed', 0)),
            feature_mode=cfg.get('feature_mode', 'base'),
            observation_space=cfg.get('observation_space', 'O_ext'),
            backend_encoding=cfg.get('backend_encoding', 'onehot'),
            stats_options=stats_options,
            public_feature_set=cfg.get('public_feature_set', 'wait_only'),
        )
        summaries[variant]['metrics']['accuracy'] = grouped['accuracy']
        summaries[variant]['metrics']['leakage_advantage'] = grouped['leakage_advantage']
        for run in runs:
            seed_name = f'{variant}_seed_{run["seed"]}.json'
            (output_dir / seed_name).write_text(json.dumps(run, indent=2), encoding='utf-8')
    output = {
        'scenario': cfg.get('scenario', 'timing_release_tradeoff'),
        'variants': variants,
        'observation_space': cfg.get('observation_space', 'O_ext'),
        'public_feature_set': cfg.get('public_feature_set', 'wait_only'),
        'scheduler_used': cfg.get('defense_scheduler') or ('secure_joint' if 'secure_joint' in cfg.get('baseline_names', []) else cfg.get('baseline_names', ['balanced'])[0]),
        'summaries': summaries,
    }
    summary_name = cfg.get('output_summary_filename', 'summary_tradeoff.json')
    (output_dir / summary_name).write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def _compile_feature_summary(jobs: list) -> dict:
    rows = []
    for job in jobs:
        features_by_backend = job.metadata.notes.get('compile_features_by_backend', {})
        if not features_by_backend:
            continue
        eligible = list(getattr(job, 'backend_eligibility', []) or features_by_backend.keys())
        selected = [features_by_backend[backend_id] for backend_id in eligible if backend_id in features_by_backend]
        if not selected:
            selected = list(features_by_backend.values())
        compiled_depth = mean([float(item.get('compiled_depth', 0.0)) for item in selected]) if selected else 0.0
        cx_count = mean([float(item.get('cx_count', 0.0)) for item in selected]) if selected else 0.0
        swap_count = mean([float(item.get('swap_count', 0.0)) for item in selected]) if selected else 0.0
        layout_span = mean([float(item.get('layout_span', 0.0)) for item in selected]) if selected else 0.0
        expected_fidelity = mean([float(item.get('expected_fidelity', 0.0)) for item in selected]) if selected else 0.0
        compile_cost = mean([float(item.get('compile_cost', 0.0)) for item in selected]) if selected else 0.0
        rows.append({
            'logical_qubits': float(job.num_qubits()),
            'logical_depth': float(job.depth()),
            'compiled_depth': compiled_depth,
            'cx_count': cx_count,
            'cx_density': (cx_count / compiled_depth) if compiled_depth > 0 else 0.0,
            'swap_count': swap_count,
            'layout_span': layout_span,
            'expected_fidelity': expected_fidelity,
            'compile_cost': compile_cost,
        })

    def pack(key: str) -> dict:
        values = [float(row[key]) for row in rows]
        return {
            'mean': round(mean(values), 4) if values else 0.0,
            'std': round(pstdev(values), 4) if len(values) > 1 else 0.0,
            'min': round(min(values), 4) if values else 0.0,
            'max': round(max(values), 4) if values else 0.0,
        }

    return {
        'num_jobs': len(rows),
        'logical_qubits': pack('logical_qubits'),
        'logical_depth': pack('logical_depth'),
        'compiled_depth': pack('compiled_depth'),
        'cx_count': pack('cx_count'),
        'cx_density': pack('cx_density'),
        'swap_count': pack('swap_count'),
        'layout_span': pack('layout_span'),
        'expected_fidelity': pack('expected_fidelity'),
        'compile_cost': pack('compile_cost'),
    }


def run_controlled_pair_compile_stats(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing_pairs_compile_stats')
    output_dir.mkdir(parents=True, exist_ok=True)
    per_seed = []
    for seed in cfg['seeds']:
        class_a = _build_probe_scenario(seed * 13 + 1, 'classA', cfg)
        class_b = _build_probe_scenario(seed * 13 + 2, 'classB', cfg)
        class_a_victims = [job for job in class_a['jobs'] if job.tenant_id == 'victim']
        class_b_victims = [job for job in class_b['jobs'] if job.tenant_id == 'victim']
        record = {
            'seed': seed,
            'classA': _compile_feature_summary(class_a_victims),
            'classB': _compile_feature_summary(class_b_victims),
        }
        per_seed.append(record)
        (output_dir / f'compile_stats_seed_{seed}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')

    fields = [
        'logical_qubits',
        'logical_depth',
        'compiled_depth',
        'cx_count',
        'cx_density',
        'swap_count',
        'layout_span',
        'expected_fidelity',
        'compile_cost',
    ]
    summary = {'scenario': cfg.get('scenario', 'timing_controlled_pair_compile_stats'), 'per_seed': per_seed, 'summary': {}}
    for cls in ['classA', 'classB']:
        summary['summary'][cls] = {}
        for field in fields:
            field_means = [float(seed_row[cls][field]['mean']) for seed_row in per_seed]
            summary['summary'][cls][field] = {
                'mean': round(mean(field_means), 4) if field_means else 0.0,
                'std': round(pstdev(field_means), 4) if len(field_means) > 1 else 0.0,
                'min': round(min(field_means), 4) if field_means else 0.0,
                'max': round(max(field_means), 4) if field_means else 0.0,
            }
    summary_name = cfg.get('compile_stats_summary_filename', 'summary_compile_stats.json')
    (output_dir / summary_name).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def run_probe_budget(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing_oext/probe_budget')
    output_dir.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    budgets = list(cfg.get('probe_budgets', [1, 5, 10, 20, 50, 220]))
    split_mode = cfg.get('probe_budget_split_mode', cfg.get('evaluation_split_mode', 'leave_one_seed_out'))
    grouped_seed = int(cfg.get('probe_budget_grouped_split_seed', cfg.get('grouped_split_seed', 0)))
    observation_space = cfg.get('observation_space', 'O_ext')
    backend_encoding = cfg.get('backend_encoding', 'onehot')
    public_feature_set = cfg.get('public_feature_set', 'wait_only')
    output = {
        'scenario': cfg.get('scenario', 'timing_probe_budget'),
        'scheduler_used': cfg.get('attack_scheduler', 'balanced'),
        'observation_space': observation_space,
        'public_feature_set': public_feature_set,
        'probe_budgets': budgets,
        'probe_budget_protocol': cfg.get('probe_budget_protocol', 'secret_bundle_loso'),
        'bundle_definition': {
            'attacker_secret_unit': cfg.get('attacker_secret_unit', 'one victim-family seed'),
            'bundle_selection_rule': cfg.get('bundle_selection_rule', 'first_k_probe_traces'),
            'bundle_feature_rule': cfg.get('bundle_feature_rule', 'bundle_summary_statistics'),
            'bundle_split_mode': split_mode,
            'grouped_split_seed': grouped_seed,
        },
        'budgets': {},
    }
    for budget in budgets:
        trial_cfg = copy.deepcopy(cfg)
        runs, aggregate = _compute_multiseed(trial_cfg)
        bundle_raw = _bundle_classifier_summary(
            *_bundle_dataset_from_runs(
                runs,
                'classA',
                'classB',
                budget=int(budget),
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        bundle_def = _bundle_classifier_summary(
            *_bundle_dataset_from_runs(
                runs,
                'classA_defended',
                'classB_defended',
                budget=int(budget),
                observation_space=observation_space,
                backend_encoding=backend_encoding,
                public_feature_set=public_feature_set,
            ),
            split_mode=split_mode,
            seed=grouped_seed,
            stats_options=stats_options,
        )
        output['budgets'][str(budget)] = {
            'probe_jobs_per_secret': int(budget),
            'metrics': {
                'accuracy': bundle_raw['accuracy'],
                'leakage_advantage': bundle_raw['leakage_advantage'],
                'threshold_accuracy': bundle_raw['threshold_accuracy'],
                'threshold_leakage_advantage': bundle_raw['threshold_leakage_advantage'],
                'defended_accuracy': bundle_def['accuracy'],
                'defended_leakage_advantage': bundle_def['leakage_advantage'],
                'defended_threshold_accuracy': bundle_def['threshold_accuracy'],
                'defended_threshold_leakage_advantage': bundle_def['threshold_leakage_advantage'],
            },
            'defense_gain': summarize(
                [bundle_raw['leakage_advantage']['mean'] - bundle_def['leakage_advantage']['mean']],
                **stats_options,
            ),
            'bundle_count_per_class': bundle_raw['num_bundle_samples_per_class'],
            'total_probe_jobs_simulated_per_secret': summarize(
                [float(run['scenarios']['classA']['probe_count']) for run in runs],
                **stats_options,
            ),
            'legacy_trace_level_reference': {
                'accuracy': aggregate['metrics']['accuracy'],
                'leakage_advantage': aggregate['metrics']['leakage_advantage'],
            },
        }
    (output_dir / cfg.get('output_summary_filename', 'summary_probe_budget.json')).write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_scheduler_oext_comparison(cfg: dict) -> dict:
    output_dir = ROOT / cfg.get('output_dir', 'results/timing_oext/scheduler_comparison')
    output_dir.mkdir(parents=True, exist_ok=True)
    schedulers = list(cfg.get('scheduler_names', ['fcfs_visible', 'jct_oriented', 'partition_fidelity_aware', 'balanced', 'secure_joint', 'randomized_backend_visible']))
    output = {
        'scenario': cfg.get('scenario', 'timing_scheduler_oext_comparison'),
        'observation_space': cfg.get('observation_space', 'O_ext'),
        'public_feature_set': cfg.get('public_feature_set', 'wait_only'),
        'schedulers': {},
    }
    for scheduler_name in schedulers:
        trial_cfg = copy.deepcopy(cfg)
        trial_cfg['attack_scheduler'] = scheduler_name
        trial_cfg['defense_scheduler'] = scheduler_name
        runs, aggregate = _compute_multiseed(trial_cfg)
        output['schedulers'][scheduler_name] = {
            'metrics': {
                'accuracy': aggregate['metrics']['accuracy'],
                'leakage_advantage': aggregate['metrics']['leakage_advantage'],
                'class_gap': aggregate['metrics']['class_gap'],
            },
            'scheduler_used_raw': scheduler_name,
            'num_seeds': len(runs),
        }
    (output_dir / cfg.get('output_summary_filename', 'summary_scheduler_comparison.json')).write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_sweep(cfg: dict) -> dict:
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    base = {k: v for k, v in cfg.items() if k != 'sweep'}
    output = {
        'scenario': cfg.get('output_label', 'timing_sweep'),
        'dimensions': {},
        'runs': {},
    }
    for dim, values in cfg['sweep'].items():
        output['dimensions'][dim] = values
        output['runs'][dim] = {}
        for value in values:
            trial_cfg = copy.deepcopy(base)
            if dim == 'observability_mode':
                trial_cfg['observability_mode'] = value
                trial_cfg['masked_mode'] = 'hardened'
            elif dim == 'workload_profile':
                trial_cfg['workload_profile'] = value
            elif dim == 'pressure_multiplier':
                trial_cfg['pressure_multiplier'] = value
            else:
                trial_cfg[dim] = value
            runs, aggregate = _compute_multiseed(trial_cfg)
            if cfg.get('store_seed_runs', False):
                output['runs'][dim][str(value)] = {
                    'aggregate': aggregate,
                    'seed_runs': runs,
                }
            else:
                output['runs'][dim][str(value)] = aggregate
    output_name = cfg.get('output_filename', 'timing_sweep.json')
    (SWEEP_DIR / output_name).write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_ablation(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    output = {'scenario': 'timing_ablation', 'ablations': {}}
    metrics = [
        'accuracy', 'leakage_advantage', 'threshold_accuracy', 'threshold_leakage_advantage',
        'defended_accuracy', 'defended_leakage_advantage', 'defended_threshold_accuracy',
        'defended_threshold_leakage_advantage', 'defense_gain'
    ]
    for variant in cfg['timing_ablations']:
        mode, profile = _defense_profile(variant)
        runs = []
        for seed in cfg['seeds']:
            runs.append(_compare_attack_and_defense(seed, cfg, mode, profile))
        output['ablations'][variant] = aggregate_metrics(runs, metrics, **stats_options)['metrics']
    (ABLATION_DIR / 'timing_ablation.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_stability(cfg: dict) -> dict:
    STABILITY_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in cfg['seeds']:
        runs.append(run_once(seed, cfg))
    defense_gains = [r['defense_gain'] for r in runs]
    positive = sum(1 for x in defense_gains if x > 0)
    stable = {
        'num_seeds': len(runs),
        'positive_gain_count': positive,
        'positive_gain_ratio': round(positive / max(len(runs), 1), 4),
        'mean_defense_gain': round(mean(defense_gains), 4) if defense_gains else 0.0,
        'std_defense_gain': round(pstdev(defense_gains), 4) if len(defense_gains) > 1 else 0.0,
        'min_defense_gain': round(min(defense_gains), 4) if defense_gains else 0.0,
        'max_defense_gain': round(max(defense_gains), 4) if defense_gains else 0.0,
        'runs': runs,
    }
    (STABILITY_DIR / 'timing_stability.json').write_text(json.dumps(stable, indent=2), encoding='utf-8')
    return stable


def run_quantum_ablation(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    metrics = [
        'accuracy',
        'leakage_advantage',
        'threshold_accuracy',
        'threshold_leakage_advantage',
        'defended_accuracy',
        'defended_leakage_advantage',
        'defended_threshold_accuracy',
        'defended_threshold_leakage_advantage',
        'defense_gain',
        'class_gap',
        'classB_minus_noVictim',
        'highIsolation_delta_from_classA',
    ]
    main_profile = cfg.get('main_profile', 'main_quantum')
    output = {
        'scenario': 'timing_quantum_ablation',
        'main_profile': main_profile,
        'ablations': {},
    }
    for name in cfg['quantum_ablations']:
        profile = _resolve_quantum_ablation_profile(name, cfg)
        runs = []
        for seed in cfg['seeds']:
            defense_mode, defense_profile = _defense_profile(cfg.get('masked_mode', 'hardened'))
            runs.append(_compare_attack_and_defense(seed, cfg, defense_mode, defense_profile, profile))
        output['ablations'][name] = {
            'profile': {
                'backend_profile': {
                'use_backend_quality_variation': profile.get('use_backend_quality_variation', True),
                'use_queue_time_variation': profile.get('use_queue_time_variation', True),
                'use_backend_utilization_variation': profile.get('use_backend_utilization_variation', True),
                'use_backend_size_heterogeneity': profile.get('use_backend_size_heterogeneity', True),
                'use_compile_path_variation': profile.get('use_compile_path_variation', True),
                'use_noise_shaping_variation': profile.get('use_noise_shaping_variation', True),
                'use_eligibility_variation': profile.get('use_eligibility_variation', True),
            },
                'pressure_profile': {
                    'use_class_dependent_pressure': profile.get('use_class_dependent_pressure', True),
                    'use_isolation_pressure_boost': profile.get('use_isolation_pressure_boost', True),
                    'use_probe_pressure_discount': profile.get('use_probe_pressure_discount', True),
                },
                'scheduler_override': profile.get('scheduler_override'),
                'defense_scheduler_override': profile.get('defense_scheduler_override'),
                'observability_mode_override': profile.get('observability_mode_override'),
            },
            'metrics': aggregate_metrics(runs, metrics, **stats_options)['metrics'],
            'runs': runs,
        }
    (ABLATION_DIR / 'timing_quantum_ablation.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_paired_contrast(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    delta_metrics = [
        'delta_accuracy',
        'delta_leakage_advantage',
        'delta_threshold_accuracy',
        'delta_threshold_leakage_advantage',
        'delta_defended_accuracy',
        'delta_defended_leakage_advantage',
        'delta_defended_threshold_accuracy',
        'delta_defended_threshold_leakage_advantage',
        'delta_defense_gain',
        'delta_class_gap',
    ]
    output = {
        'scenario': 'timing_paired_contrast',
        'reference_profile': cfg.get('reference_profile', 'main_quantum'),
        'contrasts': {},
    }
    for contrast in cfg['paired_contrasts']:
        name = contrast['name']
        reference_name = contrast.get('reference', output['reference_profile'])
        compare_name = contrast['compare']
        reference_profile = _resolve_quantum_ablation_profile(reference_name, cfg)
        compare_profile = _resolve_quantum_ablation_profile(compare_name, cfg)
        paired_runs = []
        for seed in cfg['seeds']:
            defense_mode, defense_profile = _defense_profile(cfg.get('masked_mode', 'hardened'))
            reference_run = _compare_attack_and_defense(seed, cfg, defense_mode, defense_profile, reference_profile)
            compare_run = _compare_attack_and_defense(seed, cfg, defense_mode, defense_profile, compare_profile)
            paired_runs.append({
                'seed': seed,
                'reference': reference_name,
                'compare': compare_name,
                'reference_accuracy': reference_run['accuracy'],
                'compare_accuracy': compare_run['accuracy'],
                'reference_leakage_advantage': reference_run['leakage_advantage'],
                'compare_leakage_advantage': compare_run['leakage_advantage'],
                'reference_threshold_accuracy': reference_run['threshold_accuracy'],
                'compare_threshold_accuracy': compare_run['threshold_accuracy'],
                'reference_threshold_leakage_advantage': reference_run['threshold_leakage_advantage'],
                'compare_threshold_leakage_advantage': compare_run['threshold_leakage_advantage'],
                'reference_defended_accuracy': reference_run['defended_accuracy'],
                'compare_defended_accuracy': compare_run['defended_accuracy'],
                'reference_defended_leakage_advantage': reference_run['defended_leakage_advantage'],
                'compare_defended_leakage_advantage': compare_run['defended_leakage_advantage'],
                'reference_defended_threshold_accuracy': reference_run['defended_threshold_accuracy'],
                'compare_defended_threshold_accuracy': compare_run['defended_threshold_accuracy'],
                'reference_defended_threshold_leakage_advantage': reference_run['defended_threshold_leakage_advantage'],
                'compare_defended_threshold_leakage_advantage': compare_run['defended_threshold_leakage_advantage'],
                'reference_defense_gain': reference_run['defense_gain'],
                'compare_defense_gain': compare_run['defense_gain'],
                'reference_class_gap': reference_run['class_gap'],
                'compare_class_gap': compare_run['class_gap'],
                'delta_accuracy': round(reference_run['accuracy'] - compare_run['accuracy'], 4),
                'delta_leakage_advantage': round(reference_run['leakage_advantage'] - compare_run['leakage_advantage'], 4),
                'delta_threshold_accuracy': round(reference_run['threshold_accuracy'] - compare_run['threshold_accuracy'], 4),
                'delta_threshold_leakage_advantage': round(reference_run['threshold_leakage_advantage'] - compare_run['threshold_leakage_advantage'], 4),
                'delta_defended_accuracy': round(reference_run['defended_accuracy'] - compare_run['defended_accuracy'], 4),
                'delta_defended_leakage_advantage': round(reference_run['defended_leakage_advantage'] - compare_run['defended_leakage_advantage'], 4),
                'delta_defended_threshold_accuracy': round(reference_run['defended_threshold_accuracy'] - compare_run['defended_threshold_accuracy'], 4),
                'delta_defended_threshold_leakage_advantage': round(reference_run['defended_threshold_leakage_advantage'] - compare_run['defended_threshold_leakage_advantage'], 4),
                'delta_defense_gain': round(reference_run['defense_gain'] - compare_run['defense_gain'], 4),
                'delta_class_gap': round(reference_run['class_gap'] - compare_run['class_gap'], 4),
            })
        positive = sum(1 for run in paired_runs if run['delta_leakage_advantage'] > 0)
        output['contrasts'][name] = {
            'reference': reference_name,
            'compare': compare_name,
            'description': contrast.get('description', ''),
            'metrics': {
                metric: summarize([run[metric] for run in paired_runs], **stats_options)
                for metric in delta_metrics
            },
            'positive_delta_count': positive,
            'positive_delta_ratio': round(positive / max(len(paired_runs), 1), 4),
            'runs': paired_runs,
        }
    (ABLATION_DIR / 'timing_paired_contrast.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_compile_awareness(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    metrics = [
        'accuracy',
        'leakage_advantage',
        'backend_choice_accuracy',
        'backend_choice_leakage_advantage',
        'defended_leakage_advantage',
        'defense_gain',
        'class_gap',
    ]
    reference_profile_name = cfg.get('reference_profile', 'main_quantum')
    reference_profile = _resolve_quantum_ablation_profile(reference_profile_name, cfg)
    compile_config = resolve_compile_config(
        reference_profile.get('compile_config_override') or cfg.get('compile_config')
    )
    catalog_rng = random.Random(int(cfg.get('catalog_seed', 0)))
    catalog_backends = clone_backends(
        catalog_rng,
        backend_profile={
            'use_backend_quality_variation': reference_profile.get('use_backend_quality_variation', True),
            'use_queue_time_variation': reference_profile.get('use_queue_time_variation', True),
            'use_backend_utilization_variation': reference_profile.get('use_backend_utilization_variation', True),
            'use_backend_size_heterogeneity': reference_profile.get('use_backend_size_heterogeneity', True),
            'use_compile_path_variation': reference_profile.get('use_compile_path_variation', True),
            'use_noise_shaping_variation': reference_profile.get('use_noise_shaping_variation', True),
            'heterogeneity_intensity': cfg.get('heterogeneity_intensity', 1.0),
        },
    )
    output = {
        'scenario': 'timing_compile_awareness',
        'reference_profile': reference_profile_name,
        'compile_config': compile_config,
        'compile_catalog': representative_compile_catalog(catalog_backends, compile_config),
        'profiles': {},
        'contrasts': {},
    }
    profiles = cfg.get('compile_profiles', ['main_quantum', 'compile_path_neutralized'])
    cached_runs: dict[str, list[dict]] = {}
    for name in profiles:
        profile = _resolve_quantum_ablation_profile(name, cfg)
        feature_mode = profile.get('feature_mode_override') or cfg.get('compile_feature_mode', 'compile_visible')
        runs = []
        for seed in cfg['seeds']:
            defense_mode, defense_profile = _defense_profile(cfg.get('masked_mode', 'hardened'))
            runs.append(_compare_attack_and_defense(seed, cfg, defense_mode, defense_profile, profile, feature_mode=feature_mode))
        cached_runs[name] = runs
        output['profiles'][name] = {
            'profile': {
                'feature_mode': feature_mode,
                'use_compile_path_variation': profile.get('use_compile_path_variation', True),
                'use_noise_shaping_variation': profile.get('use_noise_shaping_variation', True),
                'use_eligibility_variation': profile.get('use_eligibility_variation', True),
                'compile_config': resolve_compile_config(
                    profile.get('compile_config_override') or cfg.get('compile_config')
                ),
            },
            'metrics': aggregate_metrics(runs, metrics, **stats_options)['metrics'],
            'runs': runs,
        }
        split_mode = cfg.get('evaluation_split_mode', 'trace_holdout')
        if split_mode != 'trace_holdout':
            grouped_raw = _grouped_classifier_summary(
                *_seed_grouped_dataset(runs, 'classA', 'classB'),
                split_mode=split_mode,
                seed=int(cfg.get('grouped_split_seed', 0)),
                feature_mode=feature_mode,
                observation_space=cfg.get('observation_space', 'O_int'),
                backend_encoding=cfg.get('backend_encoding', 'onehot'),
                stats_options=stats_options,
            )
            grouped_def = _grouped_classifier_summary(
                *_seed_grouped_dataset(runs, 'classA_defended', 'classB_defended'),
                split_mode=split_mode,
                seed=int(cfg.get('grouped_split_seed', 0)),
                feature_mode=feature_mode,
                observation_space=cfg.get('observation_space', 'O_int'),
                backend_encoding=cfg.get('backend_encoding', 'onehot'),
                stats_options=stats_options,
            )
            grouped_backend = _grouped_classifier_summary(
                *_seed_grouped_dataset(runs, 'classA', 'classB'),
                split_mode=split_mode,
                seed=int(cfg.get('grouped_split_seed', 0)),
                feature_mode='backend_only',
                observation_space=cfg.get('observation_space', 'O_int'),
                backend_encoding=cfg.get('backend_encoding', 'onehot'),
                stats_options=stats_options,
            )
            output['profiles'][name]['metrics']['accuracy'] = grouped_raw['accuracy']
            output['profiles'][name]['metrics']['leakage_advantage'] = grouped_raw['leakage_advantage']
            output['profiles'][name]['metrics']['backend_choice_accuracy'] = grouped_backend['accuracy']
            output['profiles'][name]['metrics']['backend_choice_leakage_advantage'] = grouped_backend['leakage_advantage']
            output['profiles'][name]['metrics']['defended_leakage_advantage'] = grouped_def['leakage_advantage']
            output['profiles'][name]['metrics']['defense_gain'] = summarize(
                [grouped_raw['leakage_advantage']['mean'] - grouped_def['leakage_advantage']['mean']],
                **stats_options,
            )
    if len(profiles) >= 2:
        reference_name = profiles[0]
        for compare_name in profiles[1:]:
            paired = []
            for ref_run, cmp_run in zip(cached_runs[reference_name], cached_runs[compare_name]):
                paired.append({
                    'seed': ref_run['seed'],
                    'delta_leakage_advantage': round(ref_run['leakage_advantage'] - cmp_run['leakage_advantage'], 4),
                    'delta_backend_choice_leakage_advantage': round(ref_run['backend_choice_leakage_advantage'] - cmp_run['backend_choice_leakage_advantage'], 4),
                    'delta_defense_gain': round(ref_run['defense_gain'] - cmp_run['defense_gain'], 4),
                    'delta_class_gap': round(ref_run['class_gap'] - cmp_run['class_gap'], 4),
                })
            contrast_name = f'{reference_name}_vs_{compare_name}'
            positive = sum(1 for run in paired if run['delta_leakage_advantage'] > 0)
            output['contrasts'][contrast_name] = {
                'reference': reference_name,
                'compare': compare_name,
                'metrics': {
                    'delta_leakage_advantage': summarize([run['delta_leakage_advantage'] for run in paired], **stats_options),
                    'delta_backend_choice_leakage_advantage': summarize([run['delta_backend_choice_leakage_advantage'] for run in paired], **stats_options),
                    'delta_defense_gain': summarize([run['delta_defense_gain'] for run in paired], **stats_options),
                    'delta_class_gap': summarize([run['delta_class_gap'] for run in paired], **stats_options),
                },
                'positive_delta_ratio': round(positive / max(len(paired), 1), 4),
                'runs': paired,
            }
    (ABLATION_DIR / 'timing_compile_awareness.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_compile_configuration_sweep(cfg: dict) -> dict:
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    layout_methods = list(cfg.get('layout_methods', [None]))
    routing_methods = list(cfg.get('routing_methods', [None]))

    def _method_key(value):
        return 'default' if value in {None, '', 'default'} else str(value)

    output = {
        'scenario': 'timing_compile_configuration_sweep',
        'optimization_levels': list(cfg.get('optimization_levels', [0, 1, 2, 3])),
        'transpiler_seeds': list(cfg.get('transpiler_seeds', [23, 29, 31, 37])),
        'layout_methods': [_method_key(x) for x in layout_methods],
        'routing_methods': [_method_key(x) for x in routing_methods],
        'compile_profiles': list(cfg.get('compile_profiles', ['compile_visible', 'compile_path_neutralized'])),
        'reference_profile': cfg.get('reference_profile', 'compile_visible'),
        'runs': {},
    }
    for optimization_level in output['optimization_levels']:
        level_key = str(optimization_level)
        output['runs'][level_key] = {}
        for transpiler_seed in output['transpiler_seeds']:
            seed_key = str(transpiler_seed)
            output['runs'][level_key][seed_key] = {}
            for layout_method in layout_methods:
                layout_key = _method_key(layout_method)
                output['runs'][level_key][seed_key][layout_key] = {}
                for routing_method in routing_methods:
                    routing_key = _method_key(routing_method)
                    run_cfg = copy.deepcopy(cfg)
                    run_cfg['compile_config'] = {
                        'optimization_level': int(optimization_level),
                        'seed_transpiler': int(transpiler_seed),
                        'layout_method': None if layout_key == 'default' else layout_key,
                        'routing_method': None if routing_key == 'default' else routing_key,
                    }
                    result = run_compile_awareness(run_cfg)
                    output['runs'][level_key][seed_key][layout_key][routing_key] = {
                        'compile_config': result.get('compile_config', {}),
                        'profiles': {
                            name: {
                                'feature_mode': obj.get('profile', {}).get('feature_mode', 'compile_visible'),
                                'leakage_advantage': obj['metrics']['leakage_advantage']['mean'],
                                'backend_choice_leakage_advantage': obj['metrics']['backend_choice_leakage_advantage']['mean'],
                                'defense_gain': obj['metrics']['defense_gain']['mean'],
                            }
                            for name, obj in result.get('profiles', {}).items()
                        },
                        'contrasts': {
                            name: {
                                'reference': obj['reference'],
                                'compare': obj['compare'],
                                'delta_leakage_advantage': obj['metrics']['delta_leakage_advantage']['mean'],
                                'delta_leakage_ci95': obj['metrics']['delta_leakage_advantage']['ci95'],
                                'delta_backend_choice_leakage_advantage': obj['metrics']['delta_backend_choice_leakage_advantage']['mean'],
                                'delta_backend_choice_leakage_ci95': obj['metrics']['delta_backend_choice_leakage_advantage']['ci95'],
                                'positive_delta_ratio': obj['positive_delta_ratio'],
                            }
                            for name, obj in result.get('contrasts', {}).items()
                        },
                    }
    (SWEEP_DIR / 'timing_compile_configuration_sweep.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def _without_probe_jobs(scenario: dict) -> dict:
    filtered_jobs = [job for job in scenario['jobs'] if job.metadata.workload_tag != 'probe']
    filtered_pressures = {job.job_id: scenario['pressures'][job.job_id] for job in filtered_jobs}
    return {
        **scenario,
        'jobs': filtered_jobs,
        'pressures': filtered_pressures,
    }


def run_noise_heterogeneity(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    stats_options = _stats_options(cfg)
    metrics = [
        'leakage_advantage',
        'backend_choice_entropy',
        'score_margin_variance',
        'victim_mean_wait',
        'victim_fidelity_proxy_shift',
        'backend_choice_leakage_advantage',
    ]
    output = {
        'scenario': 'timing_noise_heterogeneity',
        'profiles': {},
        'contrasts': {},
    }
    cached_runs: dict[str, list[dict]] = {}
    for name in cfg.get('noise_profiles', ['uniform_noise', 'moderate_heterogeneity', 'high_drift']):
        profile = _resolve_noise_heterogeneity_profile(name, cfg)
        runs = []
        for seed in cfg['seeds']:
            defense_mode, defense_profile = _defense_profile(cfg.get('masked_mode', 'hardened'))
            main = _compare_attack_and_defense(seed, cfg, defense_mode, defense_profile, profile)
            attack_scheduler = profile.get('scheduler_override') or cfg.get('attack_scheduler') or cfg['baseline_names'][0]
            full_mode = profile.get('observability_mode_override') or cfg.get('observability_mode', 'full')
            victim_baseline = _build_probe_scenario(seed * 13 + 2, 'classB', cfg, profile)
            victim_baseline = _without_probe_jobs(victim_baseline)
            baseline_run = _run_probe_scenario(victim_baseline, attack_scheduler, full_mode, scenario_meta=victim_baseline.get('scenario_meta'))
            runs.append({
                **main,
                'noise_profile_mode': profile.get('noise_profile_mode', 'default'),
                'backend_choice_entropy': main['scenarios']['classB']['backend_choice_entropy'],
                'score_margin_variance': main['scenarios']['classB']['score_margin_variance'],
                'victim_mean_wait': main['scenarios']['classB']['victim_mean_wait'],
                'victim_mean_quality_attack': main['scenarios']['classB']['victim_mean_quality'],
                'victim_mean_quality_baseline': baseline_run['victim_mean_quality'],
                'victim_fidelity_proxy_shift': round(
                    baseline_run['victim_mean_quality'] - main['scenarios']['classB']['victim_mean_quality'],
                    4,
                ),
            })
        cached_runs[name] = runs
        output['profiles'][name] = {
            'profile': {
                'noise_profile_mode': profile.get('noise_profile_mode'),
                'heterogeneity_intensity': profile.get('heterogeneity_intensity'),
            },
            'metrics': aggregate_metrics(runs, metrics, **stats_options)['metrics'],
            'runs': runs,
        }
    reference = cfg.get('reference_profile', 'uniform_noise')
    for compare in [name for name in output['profiles'] if name != reference]:
        paired = []
        for ref_run, cmp_run in zip(cached_runs[reference], cached_runs[compare]):
            paired.append({
                'seed': ref_run['seed'],
                'delta_adv_noise': round(cmp_run['leakage_advantage'] - ref_run['leakage_advantage'], 4),
                'delta_backend_entropy': round(cmp_run['backend_choice_entropy'] - ref_run['backend_choice_entropy'], 4),
                'delta_score_margin_variance': round(cmp_run['score_margin_variance'] - ref_run['score_margin_variance'], 4),
                'delta_victim_wait': round(cmp_run['victim_mean_wait'] - ref_run['victim_mean_wait'], 4),
                'delta_fproxy_shift': round(cmp_run['victim_fidelity_proxy_shift'] - ref_run['victim_fidelity_proxy_shift'], 4),
            })
        output['contrasts'][f'{reference}_vs_{compare}'] = {
            'reference': reference,
            'compare': compare,
            'metrics': {
                'delta_adv_noise': summarize([run['delta_adv_noise'] for run in paired], **stats_options),
                'delta_backend_entropy': summarize([run['delta_backend_entropy'] for run in paired], **stats_options),
                'delta_score_margin_variance': summarize([run['delta_score_margin_variance'] for run in paired], **stats_options),
                'delta_victim_wait': summarize([run['delta_victim_wait'] for run in paired], **stats_options),
                'delta_fproxy_shift': summarize([run['delta_fproxy_shift'] for run in paired], **stats_options),
            },
            'runs': paired,
        }
    (ABLATION_DIR / 'timing_noise_heterogeneity.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output
