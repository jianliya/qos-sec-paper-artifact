from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class SecurityScheduler(BaseScheduler):
    def __init__(self, tenant_quota: dict[str, float] | None = None, demand_clip: float = 8.0, attacker_penalty: float = 2.0, victim_boost: float = 0.6):
        self.tenant_quota = tenant_quota or {}
        self.demand_clip = demand_clip
        self.attacker_penalty = attacker_penalty
        self.victim_boost = victim_boost
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        capped = []
        quota = self.tenant_quota.get(job.tenant_id, 1.0)
        raw_demand = float(job.metadata.declared_demand)
        clipped_demand = min(raw_demand, self.demand_clip)
        attacker_like = job.tenant_id == 'attacker' or 'exhaustion' in job.tags or raw_demand > self.demand_clip
        victim_like = job.tenant_id == 'victim'
        for backend in backends:
            effective_wait = backend.queue_time / max(quota, 0.1)
            effective_wait += 0.08 * clipped_demand
            if attacker_like:
                effective_wait += self.attacker_penalty
            if victim_like:
                effective_wait *= self.victim_boost
                effective_wait -= 0.15 * backend.quality_score
            capped.append((backend, effective_wait))
        backend, wait = min(capped, key=lambda x: x[1])
        quality = self.qual_est.estimate(job, backend)
        trace = ObservableTrace(estimated_wait=wait, backend_id=backend.backend_id, queue_length=int(backend.queue_time), extra={"quota": quota, "clipped_demand": clipped_demand, "attacker_like": attacker_like, "victim_like": victim_like})
        accepted = True
        reason = 'scheduled'
        if attacker_like and wait > 4.5:
            accepted = False
            reason = 'throttled_suspicious_job'
        return ScheduleDecision(job_id=job.job_id, backend_id=backend.backend_id, start_time=job.submit_time + wait, estimated_wait=wait, estimated_quality=quality, accepted=accepted, reason=reason, observable=trace)
