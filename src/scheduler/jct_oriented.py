from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends


class JCTOrientedOrchestrator(BaseOrchestrator):
    name = "jct_oriented"

    def _job_cost(self, job):
        return float(job.shots) / 1024.0 + float(job.depth_proxy) / 100.0

    def pick(self, jobs, backends, state):
        ordered = sorted(jobs, key=lambda j: (self._job_cost(j), j.submit_time))
        for job in ordered:
            candidates = eligible_backends(job, backends)
            if candidates:
                best = min(candidates, key=lambda b: (b.scarcity_score, -b.fidelity_proxy))
                return job, best
        return None, None
