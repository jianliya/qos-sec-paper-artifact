from __future__ import annotations


def build_probe_circuit(num_qubits: int = 2, depth_hint: int = 3):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(num_qubits, num_qubits)
    for i in range(depth_hint):
        qc.h(i % num_qubits)
        if num_qubits > 1:
            qc.cx(i % num_qubits, (i + 1) % num_qubits)
    qc.measure(range(num_qubits), range(num_qubits))
    return qc


def build_victim_circuit(label: str, cfg: dict | None = None):
    from qiskit import QuantumCircuit

    cfg = cfg or {}
    family = cfg.get('victim_family', 'depth_controlled')

    if family == 'legacy_width_depth':
        if label == 'classA':
            n, depth = 2, 5
        else:
            n, depth = 4, 8
        qc = QuantumCircuit(n, n)
        for i in range(depth):
            qc.rx(0.18 + 0.025 * i, i % n)
            if n > 1:
                qc.cz(i % n, (i + 1) % n)
            if label != 'classA' and i % 2 == 0:
                qc.ry(0.11 + 0.02 * i, (i + 2) % n)
        qc.measure(range(n), range(n))
        return qc

    if label == 'classA':
        n = int(cfg.get('classA_qubits', 3))
        depth = int(cfg.get('classA_depth', 18))
        ent_period = int(cfg.get('classA_entangling_period', 3))
    else:
        n = int(cfg.get('classB_qubits', 3))
        depth = int(cfg.get('classB_depth', 42))
        ent_period = int(cfg.get('classB_entangling_period', 3))

    qc = QuantumCircuit(n, n)
    for i in range(depth):
        qc.rx(0.12 + 0.01 * (i % 7), i % n)
        if n > 1 and i % max(ent_period, 1) == 0:
            qc.cz(i % n, (i + 1) % n)
    qc.measure(range(n), range(n))
    return qc
