from __future__ import annotations

from core.job import Job
from backends.backend_model import BackendModel


class ExecutionTimeEstimator:
    """Simple heuristic estimator inspired by the execution-time role in QOS."""

    def estimate(self, job: Job, backend: BackendModel) -> float:
        depth = max(job.depth(), 1)
        width = max(job.num_qubits(), 1)
        backend_factor = 1.0 + (1.0 - backend.quality_score)
        return depth * width * 0.01 * backend_factor
