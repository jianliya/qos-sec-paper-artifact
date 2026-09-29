from __future__ import annotations

from core.job import Job


def request_high_colocation_affinity(job: Job) -> Job:
    job.metadata.notes['colocation_affinity'] = 'targeted'
    job.tags.add('coloc_manipulation')
    return job
