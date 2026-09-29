from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueueState:
    now: float = 0.0
    pending_jobs: list[Any] = field(default_factory=list)
    running_jobs: list[Any] = field(default_factory=list)
    completed_jobs: list[Any] = field(default_factory=list)
