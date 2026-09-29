from __future__ import annotations


def backlog_inflation(queue_state):
    return len(queue_state.pending_jobs)


def backend_scarcity_contention(job, backends):
    eligible = [b for b in backends if b.backend_id in job.backend_eligibility]
    if not eligible:
        return 0.0
    return min(getattr(b, "scarcity_score", 0.0) for b in eligible)


def mode_priority_skew(job):
    if job.execution_mode == "session":
        return 1.0
    if job.execution_mode == "batch":
        return 0.5
    return 0.0
