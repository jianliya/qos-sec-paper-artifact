from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends


class RandomizedBackendVisibleOrchestrator(BaseOrchestrator):
    name = "randomized_backend_visible"

    def pick(self, jobs, backends, state):
        ordered = sorted(jobs, key=lambda j: (j.submit_time, j.job_id))
        for job in ordered:
            candidates = sorted(eligible_backends(job, backends), key=lambda b: b.backend_id)
            if not candidates:
                continue
            pivot = sum(ord(ch) for ch in f"{job.job_id}:{len(state.completed_jobs)}")
            return job, candidates[pivot % len(candidates)]
        return None, None
