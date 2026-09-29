from __future__ import annotations

from core.job import Job


def inflate_declared_demand(job: Job, factor: int = 2) -> Job:
    job.metadata.declared_demand *= factor
    job.tags.add('resource_inflation')
    return job
