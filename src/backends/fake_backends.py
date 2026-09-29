from __future__ import annotations

from backends.backend_model import BackendModel


def small_fake_cluster() -> list[BackendModel]:
    return [
        BackendModel(backend_id="fake_qpu_0", num_qubits=7, queue_time=1.0, quality_score=0.93),
        BackendModel(backend_id="fake_qpu_1", num_qubits=13, queue_time=2.5, quality_score=0.89),
        BackendModel(backend_id="fake_qpu_2", num_qubits=27, queue_time=4.0, quality_score=0.85),
    ]
