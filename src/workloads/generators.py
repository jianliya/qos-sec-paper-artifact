from __future__ import annotations

from core.job import Job


def make_job(
    job_id,
    tenant_id,
    submit_time,
    backend_eligibility,
    execution_mode="single",
    shots=1024,
    logical_qubits=8,
    depth_proxy=100,
    two_qubit_gate_proxy=20,
    sensitivity="normal",
    workload_role="benign",
):
    return Job(
        job_id=job_id,
        tenant_id=tenant_id,
        circuit=None,
        submit_time=submit_time,
        execution_mode=execution_mode,
        shots=shots,
        logical_qubits=logical_qubits,
        depth_proxy=depth_proxy,
        two_qubit_gate_proxy=two_qubit_gate_proxy,
        backend_eligibility=backend_eligibility,
        sensitivity=sensitivity,
        workload_role=workload_role,
    )


def make_job_from_sample(sample: dict):
    job = make_job(
        job_id=sample['job_id'],
        tenant_id=sample['tenant_id'],
        submit_time=sample['submit_time'],
        backend_eligibility=sample['backend_eligibility'],
        execution_mode=sample.get('execution_mode', 'single'),
        shots=sample.get('shots', 1024),
        logical_qubits=sample.get('logical_qubits', 8),
        depth_proxy=sample.get('depth_proxy', 100),
        two_qubit_gate_proxy=sample.get('two_qubit_gate_proxy', 20),
        sensitivity=sample.get('sensitivity', 'normal'),
        workload_role=sample.get('workload_role', 'benign'),
    )
    job.metadata.workload_tag = sample.get('workload_tag', job.metadata.workload_tag)
    job.metadata.declared_demand = sample.get('declared_demand', job.metadata.declared_demand)
    job.metadata.estimated_runtime = sample.get('estimated_runtime', job.metadata.estimated_runtime)
    job.metadata.isolation_level = sample.get('isolation_level', job.metadata.isolation_level)
    return job
