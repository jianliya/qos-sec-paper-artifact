from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from attacks.exhaustion import build_exhaustion_job
from evaluation.aggregate import aggregate_named_runs
from evaluation.metrics import percentile, safe_mean, victim_degradation_ratio
from scenarios.common import build_scheduler, clone_backends
from sim.environment import SimulationEnvironment
from utils.random_seed import set_seed
from workloads.synthetic import synthetic_job

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / 'results' / 'availability'
SWEEP_DIR = ROOT / 'results' / 'sweeps'
ABLATION_DIR = ROOT / 'results' / 'ablations'
PLOTS_DIR = ROOT / 'plots' / 'availability'


def _job_runtime(job) -> float:
    return 0.004 * max(job.depth(), 1)


def _job_pressure(job, cfg: dict, rng: random.Random) -> float:
    demand = float(job.metadata.declared_demand)
    pressure = _job_runtime(job)
    pressure += 0.02 * demand
    if 'exhaustion' in job.tags:
        pressure *= rng.uniform(cfg['attacker_saturation_min'], cfg['attacker_saturation_max'])
    if job.metadata.isolation_level == 'high':
        pressure += 0.3
    return pressure


def _build_jobs(cfg: dict, rng: random.Random):
    benign_jobs, victim_jobs, attacker_jobs = [], [], []
    for i in range(cfg['benign_jobs'] + rng.randint(0, 6)):
        benign_jobs.append(synthetic_job(f'benign-{i}', 'benign', float(max(0.0, i * 0.7 + rng.uniform(-0.18, 0.18))), max(3, 4 + (i % 5) + rng.randint(0, 1)), max(20, 30 + (i % 4) * 15 + rng.randint(-8, 12)), workload_tag='benign'))
    for i in range(cfg['victim_jobs'] + rng.randint(0, 4)):
        job = synthetic_job(f'victim-{i}', 'victim', float(max(0.0, i * 0.9 + 2.0 + rng.uniform(-0.12, 0.12))), max(6, 8 + rng.randint(-1, 1)), max(90, 120 + rng.randint(-12, 18)), workload_tag='victim')
        job.metadata.isolation_level = 'high' if i % 3 == 0 else 'normal'
        victim_jobs.append(job)
    for i in range(cfg['attacker_jobs'] + rng.randint(0, 5)):
        attacker_jobs.append(build_exhaustion_job(f'attacker-{i}', float(max(0.0, i * 0.5 + 1.0 + rng.uniform(-0.1, 0.1))), demand=max(8, cfg['attacker_demand'] + rng.randint(-2, 2)), num_qubits=max(8, 10 + rng.randint(-1, 2)), depth=max(150, 200 + rng.randint(-20, 30))))
    ordered = benign_jobs[: len(benign_jobs)//2] + attacker_jobs + victim_jobs + benign_jobs[len(benign_jobs)//2 :]
    ordered.sort(key=lambda j: j.submit_time)
    return ordered, benign_jobs, victim_jobs, attacker_jobs


def _build_seed_scenario(seed: int, cfg: dict) -> dict:
    rng = random.Random(seed * 31)
    jobs, benign_jobs, victim_jobs, attacker_jobs = _build_jobs(cfg, rng)
    pressures = {job.job_id: _job_pressure(job, cfg, rng) for job in jobs}
    backends = clone_backends(rng)
    return {
        'jobs': jobs,
        'pressures': pressures,
        'backends': backends,
        'counts': {
            'victim_jobs': len(victim_jobs),
            'attacker_jobs': len(attacker_jobs),
            'benign_jobs': len(benign_jobs),
        },
    }


def _is_blocked_record(record) -> bool:
    if not record.accepted:
        return True
    reason = str(getattr(record, 'reason', '') or '').lower()
    blocked_tokens = ('block', 'blocked', 'reject', 'rejected', 'timeout', 'timed out', 'admission')
    return any(token in reason for token in blocked_tokens)



def _run_scheduler_on_scenario(scenario: dict, scheduler_name: str, cfg: dict) -> dict:
    env = SimulationEnvironment(
        backends=copy.deepcopy(scenario['backends']),
        scheduler=build_scheduler(scheduler_name),
        rng=random.Random(0),
        observability_mode='full',
    )
    victim_waits = []
    victim_waits_all = []
    victim_blocked = 0
    attacker_waits = []
    attacker_wait_over_threshold = 0
    attacker_rejected = 0
    traces = []
    attack_delay_threshold = float(cfg.get('attack_delay_threshold', cfg.get('block_threshold', 8.0) * 0.35))
    for job in copy.deepcopy(scenario['jobs']):
        pressure = scenario['pressures'][job.job_id]
        record = env.step(job, pressure=pressure)
        if job.tenant_id == 'victim':
            victim_waits_all.append(record.estimated_wait)
            if _is_blocked_record(record):
                victim_blocked += 1
            if record.accepted:
                victim_waits.append(record.estimated_wait)
        elif job.tenant_id == 'attacker':
            attacker_waits.append(record.estimated_wait)
            if not record.accepted:
                attacker_rejected += 1
            if record.estimated_wait >= attack_delay_threshold:
                attacker_wait_over_threshold += 1
        traces.append(record.__dict__)
    attacker_job_count = scenario['counts']['attacker_jobs']
    victim_job_count = scenario['counts']['victim_jobs']
    attacker_effective_service = 1.0 - ((attacker_rejected + attacker_wait_over_threshold) / max(attacker_job_count, 1))
    return {
        'victim_avg_wait': round(safe_mean(victim_waits), 4),
        'victim_avg_wait_all': round(safe_mean(victim_waits_all), 4),
        'victim_p95_wait': round(percentile(victim_waits, 0.95), 4),
        'victim_blocked_ratio': round(victim_blocked / max(victim_job_count, 1), 4),
        'attacker_avg_wait': round(safe_mean(attacker_waits), 4),
        'attacker_p95_wait': round(percentile(attacker_waits, 0.95), 4),
        'attacker_rejected_ratio': round(attacker_rejected / max(attacker_job_count, 1), 4),
        'attacker_delay_pressure_ratio': round(attacker_wait_over_threshold / max(attacker_job_count, 1), 4),
        'attacker_effective_service': round(max(0.0, attacker_effective_service), 4),
        'avg_utilization': round(safe_mean([b.utilization for b in env.backends]), 4),
        'victim_job_count': scenario['counts']['victim_jobs'],
        'attacker_job_count': attacker_job_count,
        'benign_job_count': scenario['counts']['benign_jobs'],
        'attack_delay_threshold': round(attack_delay_threshold, 4),
        'traces': traces,
    }


def run_once(seed: int, cfg: dict) -> dict:
    set_seed(seed)
    scenario = _build_seed_scenario(seed, cfg)
    results = {}
    baseline_ref = None
    for scheduler_name in cfg['baseline_names']:
        summary = _run_scheduler_on_scenario(scenario, scheduler_name, cfg)
        results[scheduler_name] = summary
        if scheduler_name == 'queue':
            baseline_ref = summary['victim_avg_wait']
    if baseline_ref is not None:
        for name in results:
            results[name]['victim_degradation_vs_queue'] = round(victim_degradation_ratio(baseline_ref, results[name]['victim_avg_wait']), 4)
    return {'seed': seed, **results}


def _compute_multiseed(cfg: dict) -> tuple[list[dict], dict]:
    runs = []
    for seed in cfg['seeds']:
        runs.append(run_once(seed, cfg))
    aggregate = aggregate_named_runs(runs, cfg['baseline_names'], [
        'victim_avg_wait', 'victim_avg_wait_all', 'victim_p95_wait', 'victim_blocked_ratio',
        'attacker_avg_wait', 'attacker_p95_wait', 'attacker_rejected_ratio',
        'attacker_delay_pressure_ratio', 'attacker_effective_service', 'avg_utilization',
        'victim_degradation_vs_queue'
    ])
    return runs, aggregate


def run_multiseed(cfg: dict) -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    runs, aggregate = _compute_multiseed(cfg)
    for run in runs:
        (RESULTS_DIR / f"summary_seed_{run['seed']}.json").write_text(json.dumps(run, indent=2), encoding='utf-8')
    (RESULTS_DIR / 'summary_multiseed.json').write_text(json.dumps(aggregate, indent=2), encoding='utf-8')
    return aggregate


def run_sweep(cfg: dict) -> dict:
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    base = {k: v for k, v in cfg.items() if k != 'sweep'}
    sweep_spec = cfg['sweep']
    output = {'scenario': 'availability_sweep', 'dimensions': {}, 'runs': {}}
    for dim, values in sweep_spec.items():
        output['dimensions'][dim] = values
        output['runs'][dim] = {}
        for value in values:
            trial_cfg = copy.deepcopy(base)
            trial_cfg[dim] = value
            _, aggregate = _compute_multiseed(trial_cfg)
            output['runs'][dim][str(value)] = aggregate
    (SWEEP_DIR / 'availability_sweep.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output


def run_ablation(cfg: dict) -> dict:
    ABLATION_DIR.mkdir(parents=True, exist_ok=True)
    output = {'scenario': 'availability_ablation', 'ablations': {}}
    names = cfg['ablations']
    metrics = [
        'victim_avg_wait', 'victim_avg_wait_all', 'victim_p95_wait', 'victim_blocked_ratio',
        'attacker_avg_wait', 'attacker_p95_wait', 'attacker_rejected_ratio',
        'attacker_delay_pressure_ratio', 'attacker_effective_service', 'avg_utilization',
        'victim_degradation_vs_queue'
    ]
    for scheduler_name in names:
        runs = []
        for seed in cfg['seeds']:
            scenario = _build_seed_scenario(seed, cfg)
            queue_summary = _run_scheduler_on_scenario(scenario, 'queue', cfg)
            ablation_summary = _run_scheduler_on_scenario(scenario, scheduler_name, cfg)
            ablation_summary['victim_degradation_vs_queue'] = round(victim_degradation_ratio(queue_summary['victim_avg_wait'], ablation_summary['victim_avg_wait']), 4)
            runs.append({'seed': seed, scheduler_name: ablation_summary})
        output['ablations'][scheduler_name] = aggregate_named_runs(runs, [scheduler_name], metrics)['scenarios'][scheduler_name]
    (ABLATION_DIR / 'availability_ablation.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    return output
