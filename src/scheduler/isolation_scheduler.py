from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler


class IsolationScheduler(BaseScheduler):
    def __init__(self, isolation_penalty: float = 1.2):
        self.isolation_penalty = isolation_penalty
        self.qual_est = QualityEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        scored = []
        for backend in backends:
            effective_wait = backend.queue_time
            if job.metadata.isolation_level == 'high' and backend.num_qubits < max(job.num_qubits() + 2, 12):
                effective_wait += self.isolation_penalty
            scored.append((backend, effective_wait))
        backend, wait = min(scored, key=lambda x: x[1])
        quality = self.qual_est.estimate(job, backend)
        trace = ObservableTrace(estimated_wait=wait, backend_id=backend.backend_id, queue_length=int(backend.queue_time), extra={"isolation_level": job.metadata.isolation_level})
        return ScheduleDecision(job_id=job.job_id, backend_id=backend.backend_id, start_time=job.submit_time + wait, estimated_wait=wait, estimated_quality=quality, observable=trace)
