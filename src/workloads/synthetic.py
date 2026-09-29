from __future__ import annotations

from core.job import Job, JobMetadata


def synthetic_job(job_id: str, tenant_id: str, submit_time: float, num_qubits: int, depth: int, workload_tag: str = 'synthetic') -> Job:
    metadata = JobMetadata(workload_tag=workload_tag, declared_demand=max(1, num_qubits // 2), notes={'num_qubits': num_qubits, 'depth': depth})
    return Job(job_id=job_id, tenant_id=tenant_id, circuit=None, submit_time=submit_time, metadata=metadata)
