from __future__ import annotations

import time

from backends.backend_model import BackendModel


def backend_to_model(backend) -> BackendModel:
    try:
        status = backend.status()
        pending_jobs = float(getattr(status, 'pending_jobs', 0.0) or 0.0)
        operational = bool(getattr(status, 'operational', True))
    except Exception:
        pending_jobs = 0.0
        operational = True
    try:
        props = backend.properties()
        quality_proxy = 0.85
        if props and hasattr(props, 'gates') and props.gates:
            quality_proxy = max(0.4, 0.95 - min(len(props.gates) / 1000.0, 0.45))
    except Exception:
        quality_proxy = 0.8
    num_qubits = int(getattr(getattr(backend, 'configuration', lambda: None)(), 'num_qubits', 0) or getattr(backend, 'num_qubits', 0) or 0)
    return BackendModel(
        backend_id=str(getattr(backend, 'name', 'unknown_backend')),
        num_qubits=num_qubits,
        queue_time=pending_jobs,
        quality_score=quality_proxy,
        utilization=min(1.0, pending_jobs / 100.0),
        properties={
            'source': 'ibm_runtime',
            'pending_jobs': pending_jobs,
            'operational': operational,
        },
    )


def snapshot_backend(backend) -> dict:
    model = backend_to_model(backend)
    return {
        'backend_id': model.backend_id,
        'num_qubits': model.num_qubits,
        'queue_time_proxy': model.queue_time,
        'quality_score_proxy': model.quality_score,
        'utilization_proxy': model.utilization,
        'snapshot_ts': round(time.time(), 4),
        'pending_jobs': model.properties.get('pending_jobs', 0.0),
        'operational': model.properties.get('operational', True),
        'properties': model.properties,
    }
