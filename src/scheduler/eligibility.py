from __future__ import annotations


def eligible_backends(job, backends):
    return [b for b in backends if b.backend_id in job.backend_eligibility]
