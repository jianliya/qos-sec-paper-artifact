from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.execution_time import ExecutionTimeEstimator
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class BaselineScheduler(BaseScheduler):
    def __init__(self):
        self.exec_est = ExecutionTimeEstimator()
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        backend = min(backends, key=lambda b: b.queue_time)
        wait = backend.queue_time
        quality = self.qual_est.estimate(job, backend)
        start = job.submit_time + wait
        trace = ObservableTrace(estimated_wait=wait, backend_id=backend.backend_id, queue_length=int(backend.queue_time))
        return ScheduleDecision(job_id=job.job_id, backend_id=backend.backend_id, start_time=start, estimated_wait=wait, estimated_quality=quality, observable=trace)
