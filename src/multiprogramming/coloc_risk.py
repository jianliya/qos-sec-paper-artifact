from __future__ import annotations

from core.job import Job


def coloc_risk(job_a: Job, job_b: Job) -> float:
    width_factor = min((job_a.num_qubits() + job_b.num_qubits()) / max(job_a.num_qubits() + job_b.num_qubits(), 1), 1.0)
    isolation_factor = 1.0 if (job_a.metadata.isolation_level == 'high' or job_b.metadata.isolation_level == 'high') else 0.5
    return width_factor * isolation_factor
