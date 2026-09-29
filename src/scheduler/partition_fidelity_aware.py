from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends
from security.pressure_model import compute_job_pressure


class PartitionFidelityAwareOrchestrator(BaseOrchestrator):
    name = "partition_fidelity_aware"

    def _protected_backends(self, backends):
        ordered = sorted(
            backends,
            key=lambda b: (
                -float(getattr(b, "fidelity_proxy", getattr(b, "quality_score", 1.0))),
                -float(getattr(b, "qubit_capacity", getattr(b, "num_qubits", 0))),
                float(getattr(b, "scarcity_score", 0.0)),
            ),
        )
        return {ordered[0].backend_id} if ordered else set()

    def _partition_pressure(self, job, state):
        return sum(
            compute_job_pressure(pending)
            for pending in state.pending_jobs
            if pending.tenant_id == job.tenant_id and pending.job_id != job.job_id
        )

    def _partition_need(self, job):
        return (
            1.5 * float(job.num_qubits())
            + 0.5 * float(job.depth_proxy)
            + 25.0 * (1 if job.sensitivity == "sensitive" else 0)
        )

    def _score(self, job, backend, state, protected_backends, sensitive_pending):
        fidelity = float(getattr(backend, "fidelity_proxy", getattr(backend, "quality_score", 1.0)))
        capacity = float(getattr(backend, "qubit_capacity", getattr(backend, "num_qubits", 1)))
        queue_penalty = float(getattr(backend, "queue_time", 0.0))
        scarcity_penalty = 1.5 * float(getattr(backend, "scarcity_score", 0.0))
        fit_penalty = max(0.0, float(job.num_qubits()) / max(capacity, 1.0) - 0.55) * 5.0
        partition_pressure = 0.08 * self._partition_pressure(job, state)
        score = 2.2 * fidelity - queue_penalty - scarcity_penalty - fit_penalty - partition_pressure

        if backend.backend_id in protected_backends:
            if job.sensitivity == "sensitive":
                score += 2.5
            elif sensitive_pending:
                score -= 3.5

        if job.workload_role == "adversarial" and backend.backend_id in protected_backends:
            score -= 2.0

        if job.execution_mode == "session":
            score += 0.4

        score += 0.001 * self._partition_need(job)
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
