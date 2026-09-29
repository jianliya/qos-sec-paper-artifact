from __future__ import annotations

from scheduler.base_orchestrator import BaseOrchestrator
from scheduler.eligibility import eligible_backends


class LatencyNoiseAwareOrchestrator(BaseOrchestrator):
    name = "latency_noise_aware"

    def _service_demand(self, job):
        compile_cost = float(getattr(job, "estimated_compile_cost", 0.0) or 0.0)
        two_qubit = float(getattr(job, "two_qubit_gate_proxy", 0.0) or 0.0) / 200.0
        return (
            float(job.shots) / 1024.0
            + float(job.depth_proxy) / 100.0
            + two_qubit
            + compile_cost
        )

    def _predicted_latency(self, job, backend, state):
        demand = self._service_demand(job)
        queue_penalty = float(getattr(backend, "queue_time", 0.0))
        util_penalty = float(getattr(backend, "utilization", 0.0)) * 0.75
        transpile_penalty = float(
            getattr(backend, "transpilation_penalty_profile", {}).get(job.execution_mode, None)
            or getattr(backend, "transpilation_penalty_profile", {}).get("default", 1.0)
        )
        service_rate = float(getattr(backend, "base_service_rate", 1.0) or 1.0)
        backlog_penalty = 0.12 * sum(
            1 for pending in state.pending_jobs if backend.backend_id in pending.backend_eligibility
        )
        return queue_penalty + util_penalty + backlog_penalty + (demand * transpile_penalty / max(service_rate, 0.2))

    def _quality_bonus(self, job, backend):
        fidelity = float(getattr(backend, "fidelity_proxy", getattr(backend, "quality_score", 1.0)))
        qubit_fit = float(job.num_qubits()) / max(float(getattr(backend, "qubit_capacity", getattr(backend, "num_qubits", 1))), 1.0)
        scarcity = float(getattr(backend, "scarcity_score", 0.0))
        calibration_margin = 1.0 - float(getattr(backend, "utilization", 0.0))
        return 1.8 * fidelity + 0.4 * calibration_margin - 0.8 * scarcity - 0.6 * qubit_fit

    def _priority(self, job, backend, state):
        latency = self._predicted_latency(job, backend, state)
        quality_bonus = self._quality_bonus(job, backend)
        mode_penalty = 0.0 if job.execution_mode in getattr(backend, "supports_modes", [job.execution_mode]) else 4.0
        submit_bias = 0.015 * float(job.submit_time)
        return latency + mode_penalty + submit_bias - quality_bonus

    def pick(self, jobs, backends, state):
        best_pair = (None, None)
        best_score = None
        for job in jobs:
            candidates = eligible_backends(job, backends)
            for backend in candidates:
                score = self._priority(job, backend, state)
                if best_score is None or score < best_score:
                    best_score = score
                    best_pair = (job, backend)
        return best_pair
