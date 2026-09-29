from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class IBMRuntimeConfig:
    token: str | None = None
    channel: str = 'ibm_quantum'
    instance: str | None = None


class IBMRuntimeUnavailable(RuntimeError):
    pass


def load_service(cfg: dict):
    token = cfg.get('token') or os.getenv('IBM_QUANTUM_TOKEN') or os.getenv('QISKIT_IBM_TOKEN')
    if not token:
        raise IBMRuntimeUnavailable('Missing IBM Quantum token. Set IBM_QUANTUM_TOKEN or pass token in config.')
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ModuleNotFoundError as exc:
        raise IBMRuntimeUnavailable('qiskit-ibm-runtime is not installed.') from exc
    kwargs = {'channel': cfg.get('service_channel', 'ibm_quantum'), 'token': token}
    if cfg.get('instance'):
        kwargs['instance'] = cfg['instance']
    return QiskitRuntimeService(**kwargs)


def list_candidate_backends(service, max_backends: int = 2, backend_name: str | None = None):
    if backend_name:
        backend = service.backend(backend_name)
        return [backend]
    backends = []
    for backend in service.backends(simulator=False, operational=True):
        try:
            status = backend.status()
            pending = getattr(status, 'pending_jobs', 999999)
        except Exception:
            pending = 999999
        backends.append((pending, backend))
    backends.sort(key=lambda x: x[0])
    return [b for _, b in backends[:max_backends]]
