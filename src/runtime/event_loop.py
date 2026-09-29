from __future__ import annotations

from collections import defaultdict

from core.lifecycle import LifecycleRecord
from core.queue_state import QueueState


class EventLoop:
    def __init__(self, backends, scheduler):
        self.backends = {b.backend_id: b for b in backends}
        self.scheduler = scheduler
        self.state = QueueState()
        self.lifecycle = {}
        self.backend_busy_until = defaultdict(float)

    def submit_job(self, job):
        self.lifecycle[job.job_id] = LifecycleRecord(created_at=job.submit_time)
        self.lifecycle[job.job_id].queued_at = job.submit_time
        self.lifecycle[job.job_id].status = "QUEUED"
        self.state.pending_jobs.append(job)

    def step(self):
        if not self.state.pending_jobs:
            return

        self.state.now = min(max(self.state.now, j.submit_time) for j in self.state.pending_jobs)
        job, backend = self.scheduler.pick(
            self.state.pending_jobs,
            list(self.backends.values()),
            self.state,
        )

        if job is None or backend is None:
            self.state.now += 1.0
            return

        lifecycle = self.lifecycle[job.job_id]
        start_time = max(self.state.now, job.submit_time, self.backend_busy_until[backend.backend_id])
        lifecycle.dispatched_at = start_time
        lifecycle.running_at = start_time
        lifecycle.backend_id = backend.backend_id
        lifecycle.backend_quality = float(getattr(backend, 'fidelity_proxy', getattr(backend, 'quality_score', 1.0)))
        lifecycle.backend_scarcity = float(getattr(backend, 'scarcity_score', 0.0))
        lifecycle.status = "RUNNING"

        service_time = max(
            1.0,
            float(job.shots) / 1024.0 + float(job.depth_proxy) / 100.0,
        )
        finish_time = start_time + service_time
        lifecycle.finished_at = finish_time
        lifecycle.status = "DONE"

        self.backend_busy_until[backend.backend_id] = finish_time
        self.state.pending_jobs.remove(job)
        self.state.completed_jobs.append(job)
        self.state.now = finish_time

    def run_until_done(self):
        while self.state.pending_jobs:
            self.step()
        return self.lifecycle
