from __future__ import annotations

from core.job import Job
from backends.backend_model import BackendModel
from workloads.compile_aware import get_backend_compile_features


class QualityEstimator:
    """Simple fidelity/quality proxy for scheduler decisions."""

    def estimate(self, job: Job, backend: BackendModel) -> float:
        width_penalty = min(job.num_qubits() / max(backend.num_qubits, 1), 1.0) * 0.2
        depth_penalty = min(job.depth() / 1000.0, 0.2)
        compile_feats = get_backend_compile_features(job, backend)
        compile_cost = float(compile_feats.get('compile_cost', getattr(job, "estimated_compile_cost", 0.0)) or 0.0)
        two_qubit = float(compile_feats.get('cx_count', getattr(job, "two_qubit_gate_proxy", 0.0)) or 0.0)
        transpilation_penalty = float(getattr(backend, "properties", {}).get("transpilation_penalty", 1.0) or 1.0)
        noise_scale = float(getattr(backend, "properties", {}).get("noise_scale", max(0.0, 1.0 - float(backend.quality_score))) or 0.0)
        compile_penalty = min(0.16, 0.018 * compile_cost * transpilation_penalty + 0.002 * float(compile_feats.get('swap_count', 0.0)))
        entangling_penalty = min(0.12, two_qubit / max(float(backend.num_qubits), 1.0) / 36.0)
        noise_penalty = min(0.1, 0.18 * noise_scale)
        compile_expected = float(compile_feats.get('expected_fidelity', backend.quality_score))
        return max(0.0, min(0.99, compile_expected - width_penalty - depth_penalty - compile_penalty - entangling_penalty - noise_penalty))
