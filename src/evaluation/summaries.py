from __future__ import annotations

from statistics import mean

from core.metrics import queue_wait, turnaround_time
from evaluation.metrics import percentile
from security.pressure_model import compute_tenant_pressure


def _safe_mean(values):
    vals = [v for v in values if v is not None]
    return mean(vals) if vals else 0.0


def _safe_max(values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else 0.0


def _safe_ratio(num: float, den: float) -> float:
    if abs(den) <= 1e-9:
        return 0.0
    return float(num / den)


def _fairness_index(values):
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    denom = len(vals) * sum(v * v for v in vals)
    if denom == 0:
        return 0.0
    return (sum(vals) ** 2) / denom


def _service_demand(job):
    return max(
        1.0,
        float(job.shots) / 1024.0 + float(job.depth_proxy) / 100.0,
    )


def summarize_job_metrics(jobs, lifecycle):
    jobs_by_id = {job.job_id: job for job in jobs}
    result = {}
    for job_id, record in lifecycle.items():
        job = jobs_by_id.get(job_id)
        demand = _service_demand(job) if job is not None else 1.0
        turn = turnaround_time(record) or 0.0
        result[job_id] = {
            'queue_wait': queue_wait(record),
            'turnaround_time': turnaround_time(record),
            'service_demand': demand,
            'slowdown_ratio': _safe_ratio(turn, demand),
            'backend_id': record.backend_id,
            'backend_quality': record.backend_quality,
            'backend_scarcity': record.backend_scarcity,
            'status': record.status,
        }
    return result


def summarize_tenant_metrics(jobs, lifecycle):
    tenants = sorted({job.tenant_id for job in jobs})
    result = {}
    for tenant_id in tenants:
        tenant_jobs = [job for job in jobs if job.tenant_id == tenant_id]
        waits = [queue_wait(lifecycle[j.job_id]) for j in tenant_jobs]
        turns = [turnaround_time(lifecycle[j.job_id]) for j in tenant_jobs]
        service = [_service_demand(j) for j in tenant_jobs]
        slowdowns = [
            _safe_ratio(turnaround_time(lifecycle[j.job_id]) or 0.0, _service_demand(j))
            for j in tenant_jobs
        ]
        result[tenant_id] = {
            'num_jobs': len(tenant_jobs),
            'mean_wait': _safe_mean(waits),
            'p95_wait': percentile([w for w in waits if w is not None], 0.95),
            'p99_wait': percentile([w for w in waits if w is not None], 0.99),
            'mean_turnaround': _safe_mean(turns),
            'mean_service_demand': _safe_mean(service),
            'slowdown_ratio': _safe_mean(slowdowns),
            'pressure': compute_tenant_pressure(tenant_jobs, tenant_id),
            'sensitive_jobs': sum(1 for j in tenant_jobs if j.sensitivity == 'sensitive'),
            'role': tenant_jobs[0].workload_role if tenant_jobs else 'unknown',
        }
    return result


def summarize_victim_metrics(jobs, lifecycle):
    victim_jobs = [job for job in jobs if job.sensitivity == 'sensitive']
    waits = [queue_wait(lifecycle[j.job_id]) for j in victim_jobs]
    turns = [turnaround_time(lifecycle[j.job_id]) for j in victim_jobs]
    slowdowns = [
        _safe_ratio(turnaround_time(lifecycle[j.job_id]) or 0.0, _service_demand(j))
        for j in victim_jobs
    ]
    return {
        'num_victim_jobs': len(victim_jobs),
        'victim_mean_wait': _safe_mean(waits),
        'victim_p95_wait': percentile([w for w in waits if w is not None], 0.95),
        'victim_p99_wait': percentile([w for w in waits if w is not None], 0.99),
        'victim_mean_turnaround': _safe_mean(turns),
        'victim_slowdown_ratio': _safe_mean(slowdowns),
    }


def summarize_attacker_metrics(jobs, lifecycle):
    attacker_jobs = [job for job in jobs if job.workload_role == 'adversarial']
    waits = [queue_wait(lifecycle[j.job_id]) for j in attacker_jobs]
    turns = [turnaround_time(lifecycle[j.job_id]) for j in attacker_jobs]
    service = [_service_demand(j) for j in attacker_jobs]
    pressure_ratios = [
        _safe_ratio(queue_wait(lifecycle[j.job_id]) or 0.0, _service_demand(j))
        for j in attacker_jobs
    ]
    utility = [
        _safe_ratio(_service_demand(j), turnaround_time(lifecycle[j.job_id]) or _service_demand(j))
        for j in attacker_jobs
    ]
    return {
        'num_attacker_jobs': len(attacker_jobs),
        'attacker_mean_wait': _safe_mean(waits),
        'attacker_mean_turnaround': _safe_mean(turns),
        'attacker_pressure': compute_tenant_pressure(attacker_jobs, attacker_jobs[0].tenant_id) if attacker_jobs else 0.0,
        'attacker_delay_pressure_ratio': _safe_mean(pressure_ratios),
        'DPR_A': _safe_mean(pressure_ratios),
        'attacker_effective_service': _safe_mean(utility),
        'attacker_mean_service_demand': _safe_mean(service),
    }


def summarize_system_metrics(jobs, lifecycle):
    waits = [queue_wait(record) for record in lifecycle.values()]
    turns = [turnaround_time(record) for record in lifecycle.values()]
    tenant_metrics = summarize_tenant_metrics(jobs, lifecycle)
    created = [record.created_at for record in lifecycle.values() if record.created_at is not None]
    finished = [record.finished_at for record in lifecycle.values() if record.finished_at is not None]
    makespan = (max(finished) - min(created)) if created and finished else 0.0
    backend_quality_costs = [
        max(0.0, 1.0 - float(record.backend_quality))
        for record in lifecycle.values()
        if record.backend_quality is not None
    ]
    system_mean_wait = _safe_mean(waits)
    worst_tenant_wait = _safe_max([obj.get('mean_wait', 0.0) for obj in tenant_metrics.values()])
    return {
        'num_jobs': len(jobs),
        'mean_wait': system_mean_wait,
        'mean_turnaround': _safe_mean(turns),
        'completed_jobs': sum(1 for record in lifecycle.values() if record.status == 'DONE'),
        'throughput': _safe_ratio(sum(1 for record in lifecycle.values() if record.status == 'DONE'), makespan),
        'wait_fairness': _fairness_index(waits),
        'turnaround_fairness': _fairness_index(turns),
        'worst_tenant_degradation': max(0.0, _safe_ratio(worst_tenant_wait, system_mean_wait if system_mean_wait > 0 else 1.0) - 1.0),
        'fidelity_proxy_cost': _safe_mean(backend_quality_costs),
    }


def summarize_all(jobs, lifecycle):
    return {
        'job_metrics': summarize_job_metrics(jobs, lifecycle),
        'tenant_metrics': summarize_tenant_metrics(jobs, lifecycle),
        'victim_metrics': summarize_victim_metrics(jobs, lifecycle),
        'attacker_metrics': summarize_attacker_metrics(jobs, lifecycle),
        'system_metrics': summarize_system_metrics(jobs, lifecycle),
    }
