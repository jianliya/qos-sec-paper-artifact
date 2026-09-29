from __future__ import annotations


def compute_tenant_pressure(jobs, tenant_id):
    tenant_jobs = [j for j in jobs if j.tenant_id == tenant_id]
    if not tenant_jobs:
        return 0.0
    return sum(float(j.shots) / 1024.0 + float(j.depth_proxy) / 100.0 for j in tenant_jobs)


def compute_job_pressure(job):
    return float(job.shots) / 1024.0 + float(job.depth_proxy) / 100.0
