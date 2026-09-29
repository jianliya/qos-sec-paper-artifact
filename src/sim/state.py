from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationRecord:
    job_id: str
    tenant_id: str
    workload_tag: str
    backend_id: str
    accepted: bool
    reason: str
    estimated_wait: float
    estimated_quality: float
    observed: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendSnapshot:
    backend_id: str
    queue_time: float
    utilization: float
    quality_score: float
