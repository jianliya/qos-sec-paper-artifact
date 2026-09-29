from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class QualityFirstScheduler(BaseScheduler):
    def __init__(self):
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        scored = []
        for backend in backends:
            quality = self.qual_est.estimate(job, backend)
            scored.append((backend, quality, float(backend.queue_time)))
        backend, quality, wait = max(scored, key=lambda x: (x[1], -x[2]))
        trace = ObservableTrace(
            estimated_wait=wait,
            backend_id=backend.backend_id,
            queue_length=int(backend.queue_time),
            extra={"quality_priority": quality},
        )
        return ScheduleDecision(
            job_id=job.job_id,
            backend_id=backend.backend_id,
            start_time=job.submit_time + wait,
            estimated_wait=wait,
            estimated_quality=quality,
            observable=trace,
        )
