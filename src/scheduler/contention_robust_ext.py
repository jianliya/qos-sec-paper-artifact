from __future__ import annotations

from scheduler.contention_robust import ContentionRobustOrchestrator
from scheduler.eligibility import eligible_backends


class ContentionRobustExtOrchestrator(ContentionRobustOrchestrator):
    name = "contention_robust_ext"

    def __init__(
        self,
        enable_compatibility_awareness: bool = True,
        enable_sensitivity_protection: bool = True,
        enable_pressure_budget: bool = True,
        pressure_budget_threshold: float = 5.0,
        enable_fallback_cap: bool = True,
        attacker_pending_share_cap: float = 0.34,
        reserve_best_backend: bool = True,
    ):
        super().__init__(
            enable_compatibility_awareness=enable_compatibility_awareness,
            enable_sensitivity_protection=enable_sensitivity_protection,
            enable_pressure_budget=enable_pressure_budget,
            pressure_budget_threshold=pressure_budget_threshold,
        )
        self.enable_fallback_cap = enable_fallback_cap
        self.attacker_pending_share_cap = attacker_pending_share_cap
        self.reserve_best_backend = reserve_best_backend

    def _protected_backends(self, backends):
        ordered = sorted(
            backends,
            key=lambda b: (
                -float(getattr(b, "fidelity_proxy", getattr(b, "quality_score", 1.0))),
                float(getattr(b, "scarcity_score", 0.0)),
                -float(getattr(b, "qubit_capacity", getattr(b, "num_qubits", 0))),
            ),
        )
        return {ordered[0].backend_id} if ordered and self.reserve_best_backend else set()

    def _attacker_pending_share(self, jobs):
        if not jobs:
            return 0.0
        return sum(1 for job in jobs if job.workload_role == "adversarial") / len(jobs)

    def _fallback_active(self, jobs):
        sensitive_pending = any(job.sensitivity == "sensitive" for job in jobs)
        attacker_share = self._attacker_pending_share(jobs)
        return self.enable_fallback_cap and sensitive_pending and attacker_share >= self.attacker_pending_share_cap

    def _fallback_filtered_pairs(self, jobs, backends):
        protected_backends = self._protected_backends(backends)
        filtered = []
        for job in jobs:
            if job.workload_role == "adversarial":
                continue
            for backend in eligible_backends(job, backends):
                if protected_backends and backend.backend_id in protected_backends and job.sensitivity != "sensitive":
                    continue
                filtered.append((job, backend))
        return filtered, protected_backends

    def pick(self, jobs, backends, state):
        if self._fallback_active(jobs):
            filtered, protected_backends = self._fallback_filtered_pairs(jobs, backends)
            best_pair = (None, None)
            best_score = None
            for job, backend in filtered:
                score = self._score(job, backend, state)
                if protected_backends and backend.backend_id in protected_backends:
                    score += 1.5
                if best_score is None or score > best_score:
                    best_score = score
                    best_pair = (job, backend)
            if best_pair != (None, None):
                return best_pair
        return super().pick(jobs, backends, state)
