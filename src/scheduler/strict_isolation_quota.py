from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends
from security.pressure_model import compute_job_pressure


class StrictIsolationQuotaOrchestrator(BaseOrchestrator):
    name = "strict_isolation_quota"

    def __init__(
        self,
        adversarial_pressure_penalty: float = 2.0,
        adversarial_quota: float = 0.55,
        sensitive_quota: float = 1.6,
        benign_quota: float = 1.0,
    ):
        self.adversarial_pressure_penalty = adversarial_pressure_penalty
        self.adversarial_quota = adversarial_quota
        self.sensitive_quota = sensitive_quota
        self.benign_quota = benign_quota

    def _tenant_quota(self, job):
        if job.sensitivity == "sensitive":
            return self.sensitive_quota
        if job.workload_role == "adversarial":
            return self.adversarial_quota
        return self.benign_quota

    def _protected_backends(self, backends):
        ordered = sorted(
            backends,
            key=lambda b: (
                -float(getattr(b, "fidelity_proxy", getattr(b, "quality_score", 1.0))),
                -float(getattr(b, "qubit_capacity", getattr(b, "num_qubits", 0))),
            ),
        )
        return {ordered[0].backend_id} if ordered else set()

    def _tenant_pending_share(self, job, state):
        total = max(len(state.pending_jobs), 1)
        same_tenant = sum(1 for pending in state.pending_jobs if pending.tenant_id == job.tenant_id)
        return same_tenant / total

    def _score(self, job, backend, state, protected_backends, sensitive_pending):
        quota = self._tenant_quota(job)
        queue_penalty = float(getattr(backend, "queue_time", 0.0)) / max(quota, 0.1)
        pressure_penalty = compute_job_pressure(job) * 0.1
        share_penalty = self._tenant_pending_share(job, state)
        scarcity_penalty = float(getattr(backend, "scarcity_score", 0.0))
        score = -(queue_penalty + pressure_penalty + scarcity_penalty + 2.0 * share_penalty)

        if job.sensitivity == "sensitive":
            score += 4.0
        if job.workload_role == "adversarial":
            score -= self.adversarial_pressure_penalty

        if backend.backend_id in protected_backends:
            if job.sensitivity == "sensitive":
                score += 1.5
            elif sensitive_pending:
                score -= 4.0

        if job.workload_role == "adversarial" and share_penalty > 0.35:
            score -= 2.5

        return score

    def pick(self, jobs, backends, state):
        protected_backends = self._protected_backends(backends)
        sensitive_pending = any(job.sensitivity == "sensitive" for job in jobs)
        best_pair = (None, None)
        best_score = None
        for job in jobs:
            candidates = eligible_backends(job, backends)
            for backend in candidates:
                score = self._score(job, backend, state, protected_backends, sensitive_pending)
                if best_score is None or score > best_score:
                    best_score = score
                    best_pair = (job, backend)
        return best_pair
