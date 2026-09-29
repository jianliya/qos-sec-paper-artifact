from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends


class NaiveIsolationOrchestrator(BaseOrchestrator):
    name = "naive_isolation"

    def pick(self, jobs, backends, state):
        ordered = sorted(
            jobs,
            key=lambda j: (
                0 if j.sensitivity == "sensitive" else 1,
                j.submit_time,
            ),
        )
        for job in ordered:
            candidates = eligible_backends(job, backends)
            if not candidates:
                continue
            if job.sensitivity == "sensitive":
                best = min(candidates, key=lambda b: (b.scarcity_score, -b.fidelity_proxy))
            else:
                best = candidates[0]
            return job, best
        return None, None
