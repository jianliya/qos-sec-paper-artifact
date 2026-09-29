from __future__ import annotations

from core.job import Job, JobMetadata


def build_probe_job(job_id: str, submit_time: float, num_qubits: int = 2, depth: int = 8) -> Job:
    metadata = JobMetadata(workload_tag='probe', declared_demand=1, notes={'num_qubits': num_qubits, 'depth': depth})
    return Job(job_id=job_id, tenant_id='attacker', circuit=None, submit_time=submit_time, metadata=metadata)
