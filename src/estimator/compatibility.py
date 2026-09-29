from __future__ import annotations

from core.job import Job
from backends.backend_model import BackendModel


class CompatibilityEstimator:
    """QOS-inspired compatibility approximation for co-location decisions."""

    def score(self, job_a: Job, job_b: Job, backend: BackendModel) -> float:
        width_term = 1.0 - min((job_a.num_qubits() + job_b.num_qubits()) / max(backend.num_qubits, 1), 1.0)
        depth_gap = abs(job_a.depth() - job_b.depth())
        depth_term = max(0.0, 1.0 - depth_gap / 1000.0)
        isolation_penalty = 0.2 if (job_a.metadata.isolation_level == 'high' or job_b.metadata.isolation_level == 'high') else 0.0
        return max(0.0, (width_term + depth_term) / 2.0 - isolation_penalty)
