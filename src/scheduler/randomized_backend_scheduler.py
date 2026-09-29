from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class RandomizedBackendScheduler(BaseScheduler):
    def __init__(self):
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        ordered = sorted(backends, key=lambda b: b.backend_id)
        pivot = sum(ord(ch) for ch in job.job_id) % max(len(ordered), 1)
        backend = ordered[pivot]
        wait = float(backend.queue_time)
        quality = self.qual_est.estimate(job, backend)
        trace = ObservableTrace(
            estimated_wait=wait,
            backend_id=backend.backend_id,
            queue_length=int(backend.queue_time),
            extra={"selection_mode": "deterministic_randomized"},
        )
        return ScheduleDecision(
            job_id=job.job_id,
            backend_id=backend.backend_id,
            start_time=job.submit_time + wait,
            estimated_wait=wait,
            estimated_quality=quality,
            observable=trace,
        )
