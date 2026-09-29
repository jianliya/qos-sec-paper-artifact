from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObservableTrace:
    estimated_wait: float
    backend_id: str
    queue_length: int
    colocated_job_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleDecision:
    job_id: str
    backend_id: str
    start_time: float
    estimated_wait: float
    estimated_quality: float
    colocated_job_ids: list[str] = field(default_factory=list)
    accepted: bool = True
    reason: str = "scheduled"
    observable: ObservableTrace | None = None
