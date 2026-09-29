from __future__ import annotations

from backends.backend_model import BackendModel


def load_ibm_fake_backends() -> list[BackendModel]:
    """Create lightweight backend profiles.

    Prefer Qiskit GenericBackendV2 when available; otherwise fall back to
    local static backend profiles so the paper experiments remain runnable in
    lightweight environments.
    """
    try:
        from qiskit.providers.fake_provider import GenericBackendV2  # type: ignore

        fake_instances = [
            GenericBackendV2(num_qubits=7, basis_gates=['id', 'rz', 'sx', 'x', 'cx']),
            GenericBackendV2(num_qubits=13, basis_gates=['id', 'rz', 'sx', 'x', 'cx']),
            GenericBackendV2(num_qubits=27, basis_gates=['id', 'rz', 'sx', 'x', 'cx']),
        ]

        backends: list[BackendModel] = []
        for idx, backend in enumerate(fake_instances):
            num_qubits = int(getattr(backend, 'num_qubits', 0) or 0)
            backends.append(
                BackendModel(
                    backend_id=f'generic_fake_{idx}',
                    num_qubits=num_qubits,
                    queue_time=float(idx + 1),
                    quality_score=max(0.5, 0.95 - idx * 0.05),
                    utilization=0.2 * idx,
                    properties={'source': 'qiskit_generic_backend_v2', 'backend_obj': backend},
                )
            )
        return backends
    except ModuleNotFoundError:
        return [
            BackendModel(backend_id='fallback_fake_0', num_qubits=7, queue_time=1.0, quality_score=0.95, utilization=0.05, properties={'source': 'fallback_profile'}),
            BackendModel(backend_id='fallback_fake_1', num_qubits=13, queue_time=2.0, quality_score=0.9, utilization=0.2, properties={'source': 'fallback_profile'}),
            BackendModel(backend_id='fallback_fake_2', num_qubits=27, queue_time=3.0, quality_score=0.85, utilization=0.4, properties={'source': 'fallback_profile'}),
        ]
