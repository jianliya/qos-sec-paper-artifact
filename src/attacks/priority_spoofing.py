from __future__ import annotations

from core.job import Job


def spoof_priority(job: Job, new_priority: int = 10) -> Job:
    job.priority = new_priority
    job.tags.add('priority_spoofing')
    return job
