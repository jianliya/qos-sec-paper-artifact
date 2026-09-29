from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends
from security.pressure_model import compute_job_pressure
from security.degradation_model import backend_scarcity_contention, mode_priority_skew


class ContentionRobustOrchestrator(BaseOrchestrator):
    name = "contention_robust"

    def __init__(
        self,
        enable_compatibility_awareness: bool = True,
        enable_sensitivity_protection: bool = True,
        enable_pressure_budget: bool = True,
        pressure_budget_threshold: float = 5.0,
    ):
        self.enable_compatibility_awareness = enable_compatibility_awareness
        self.enable_sensitivity_protection = enable_sensitivity_protection
        self.enable_pressure_budget = enable_pressure_budget
        self.pressure_budget_threshold = pressure_budget_threshold

    def _score(self, job, backend, state):
        score = 0.0

        if self.enable_sensitivity_protection and job.sensitivity == "sensitive":
            score += 5.0

        if self.enable_compatibility_awareness:
            scarcity = backend_scarcity_contention(job, [backend])
            score -= scarcity * 2.0

        if self.enable_pressure_budget:
            pressure = compute_job_pressure(job)
            if pressure > self.pressure_budget_threshold:
                score -= 3.0

        score -= mode_priority_skew(job) * 0.5
        score -= pressure_based_arrival_penalty(job)
        return score

    def pick(self, jobs, backends, state):
        best_pair = (None, None)
        best_score = None
        for job in jobs:
            candidates = eligible_backends(job, backends)
            for backend in candidates:
                score = self._score(job, backend, state)
                if best_score is None or score > best_score:
                    best_score = score
                    best_pair = (job, backend)
        return best_pair


def pressure_based_arrival_penalty(job):
    pressure = compute_job_pressure(job)
    return pressure * 0.1 + job.submit_time * 0.001
