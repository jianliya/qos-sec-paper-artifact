from __future__ import annotations

from core.job import Job, JobMetadata


def build_exhaustion_job(job_id: str, submit_time: float, demand: int = 10, num_qubits: int = 8, depth: int = 100) -> Job:
    metadata = JobMetadata(workload_tag='exhaustion', declared_demand=demand, notes={'num_qubits': num_qubits, 'depth': depth})
    job = Job(job_id=job_id, tenant_id='attacker', circuit=None, submit_time=submit_time, metadata=metadata)
    job.tags.add('exhaustion')
    return job
