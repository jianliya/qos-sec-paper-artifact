from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends


class FCFSVisibleOrchestrator(BaseOrchestrator):
    name = "fcfs_visible"

    def pick(self, jobs, backends, state):
        ordered = sorted(jobs, key=lambda j: j.submit_time)
        for job in ordered:
            candidates = eligible_backends(job, backends)
            if candidates:
                return job, candidates[0]
        return None, None
