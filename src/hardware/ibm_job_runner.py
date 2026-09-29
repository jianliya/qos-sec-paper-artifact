from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class HardwareRunRecord:
    job_id: str
    backend_id: str
    submit_ts: float
    end_ts: float
    latency: float
    shots: int
    status: str
    counts: dict | None = None
    num_qubits: int | None = None
    depth: int | None = None
    size: int | None = None
    two_qubit_gates: int | None = None


def _build_isa_circuit(backend, circuit):
    try:
        from qiskit import transpile
        return transpile(circuit, backend=backend, optimization_level=1)
    except Exception:
        return circuit


def _circuit_stats(circuit) -> dict:
    try:
        ops = circuit.count_ops()
    except Exception:
        ops = {}
    two_qubit_gates = 0
    for gate, count in ops.items():
        if gate in {'cx', 'cz', 'ecr', 'swap', 'iswap'}:
            two_qubit_gates += int(count)
    try:
        depth = int(circuit.depth())
    except Exception:
        depth = 0
    try:
        size = int(circuit.size())
    except Exception:
        size = 0
    try:
        num_qubits = int(circuit.num_qubits)
    except Exception:
        num_qubits = 0
    return {
        'num_qubits': num_qubits,
        'depth': depth,
        'size': size,
        'two_qubit_gates': two_qubit_gates,
    }


def run_sampler_job(backend, circuit, shots: int = 64) -> HardwareRunRecord:
    submit_ts = time.time()
    try:
        from qiskit_ibm_runtime import SamplerV2 as Sampler
    except ModuleNotFoundError:
        from qiskit_ibm_runtime import Sampler  # type: ignore
    isa_circuit = _build_isa_circuit(backend, circuit)
    stats = _circuit_stats(isa_circuit)
    sampler = Sampler(mode=backend)
    job = sampler.run([(isa_circuit,)], shots=shots)
    result = job.result()
    end_ts = time.time()
    counts = None
    try:
        pub_res = result[0]
        data = getattr(pub_res, 'data', None)
        if data is not None and hasattr(data, 'meas') and hasattr(data.meas, 'get_counts'):
            counts = data.meas.get_counts()
    except Exception:
        counts = None
    return HardwareRunRecord(
        job_id=str(job.job_id()),
        backend_id=str(getattr(backend, 'name', 'unknown_backend')),
        submit_ts=submit_ts,
        end_ts=end_ts,
        latency=end_ts - submit_ts,
        shots=shots,
        status='completed',
        counts=counts,
        num_qubits=stats['num_qubits'],
        depth=stats['depth'],
        size=stats['size'],
        two_qubit_gates=stats['two_qubit_gates'],
    )
