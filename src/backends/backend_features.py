from __future__ import annotations

from backends.backend_model import BackendModel


def backend_feature_vector(backend: BackendModel) -> dict:
    return {
        "backend_id": backend.backend_id,
        "num_qubits": backend.num_qubits,
        "queue_time": backend.queue_time,
        "quality_score": backend.quality_score,
        "utilization": backend.utilization,
    }
