from __future__ import annotations

from core.job import Job
from backends.backend_model import BackendModel
from workloads.compile_aware import get_backend_compile_features


class RiskEstimator:
    @staticmethod
    def _clip(value: float) -> float:
        return min(1.0, max(0.0, value))

    def exhaustion_risk(self, job: Job) -> float:
        demand = float(job.metadata.declared_demand)
        depth = float(job.depth())
        risk = 0.04 * demand + min(depth / 500.0, 0.6)
        if job.tenant_id == 'attacker' or 'exhaustion' in job.tags:
            risk += 0.5
        return self._clip(risk)

    def timing_leakage_risk(self, job: Job) -> float:
        if job.metadata.isolation_level == 'high':
            return 0.85
        if job.metadata.workload_tag in {'classB', 'victim'}:
            return 0.55
        return 0.2

    def backend_exhaustion_risk(self, job: Job, backend: BackendModel) -> float:
        base = self.exhaustion_risk(job)
        load = min(backend.queue_time / 2.0, 1.0)
        util = min(max(backend.utilization, 0.0), 1.0)
        size_pressure = min(job.num_qubits() / max(backend.num_qubits, 1), 1.0)
        demand_pressure = min(float(job.metadata.declared_demand) / max(backend.num_qubits, 1), 1.0)
        risk = 0.35 * base + 0.3 * load + 0.2 * util + 0.075 * size_pressure + 0.075 * demand_pressure
        return self._clip(risk)

    def backend_timing_leakage_risk(self, job: Job, backend: BackendModel) -> float:
        base = self.timing_leakage_risk(job)
        contention = min(backend.queue_time / 2.0, 1.0)
        tightness = min(job.num_qubits() / max(backend.num_qubits, 1), 1.0)
        compile_feats = get_backend_compile_features(job, backend)
        compile_cost = float(compile_feats.get('compile_cost', getattr(job, "estimated_compile_cost", 0.0)) or 0.0)
        transpilation_penalty = float(getattr(backend, "properties", {}).get("transpilation_penalty", 1.0) or 1.0)
        noise_scale = float(getattr(backend, "properties", {}).get("noise_scale", 0.0) or 0.0)
        crosstalk_risk = float(getattr(backend, "properties", {}).get("crosstalk_risk", 0.0) or 0.0)
        compile_mismatch = min(1.0, 0.06 * compile_cost * transpilation_penalty + 0.02 * float(compile_feats.get('swap_count', 0.0)))
        placement_exposure = min(1.0, 0.04 * float(compile_feats.get('layout_span', 0.0)) + 0.12 * (1.0 - float(compile_feats.get('backend_suitability', 1.0))))
        exposure = 0.38 * base + 0.22 * contention + 0.14 * tightness + 0.11 * compile_mismatch + 0.07 * placement_exposure + 0.05 * noise_scale + 0.03 * crosstalk_risk
        if job.metadata.isolation_level == 'high' and backend.num_qubits < max(job.num_qubits() + 2, 12):
            exposure += 0.2
        return self._clip(exposure)
