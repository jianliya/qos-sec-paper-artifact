from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LifecycleRecord:
    created_at: float
    queued_at: Optional[float] = None
    dispatched_at: Optional[float] = None
    running_at: Optional[float] = None
    finished_at: Optional[float] = None
    backend_id: Optional[str] = None
    backend_quality: Optional[float] = None
    backend_scarcity: Optional[float] = None
    status: str = "CREATED"
