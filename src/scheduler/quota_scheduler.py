from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class QuotaScheduler(BaseScheduler):
    def __init__(self, tenant_quota: dict[str, float] | None = None):
        self.tenant_quota = tenant_quota or {}
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        quota = self.tenant_quota.get(job.tenant_id, 1.0)
        scored = []
        for backend in backends:
            effective_wait = backend.queue_time / max(quota, 0.1)
            scored.append((backend, effective_wait))
        backend, wait = min(scored, key=lambda x: x[1])
        quality = self.qual_est.estimate(job, backend)
        trace = ObservableTrace(estimated_wait=wait, backend_id=backend.backend_id, queue_length=int(backend.queue_time), extra={"quota": quota})
        return ScheduleDecision(job_id=job.job_id, backend_id=backend.backend_id, start_time=job.submit_time + wait, estimated_wait=wait, estimated_quality=quality, observable=trace)
