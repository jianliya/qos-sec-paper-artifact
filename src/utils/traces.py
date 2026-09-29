from __future__ import annotations

from core.decision import ScheduleDecision


def decision_to_trace(decision: ScheduleDecision) -> dict:
    return {
        'job_id': decision.job_id,
        'backend_id': decision.backend_id,
        'start_time': decision.start_time,
        'estimated_wait': decision.estimated_wait,
        'estimated_quality': decision.estimated_quality,
        'accepted': decision.accepted,
        'reason': decision.reason,
        'observable': None if decision.observable is None else decision.observable.__dict__,
    }
