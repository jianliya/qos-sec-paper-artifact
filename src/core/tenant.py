from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tenant:
    tenant_id: str
    role: str = "benign"
    arrival_profile: dict = field(default_factory=dict)
    priority_class: str = "default"
    historical_service: float = 0.0
    current_backlog: int = 0
    recent_pressure: float = 0.0
    fairness_debt: float = 0.0
    quota: float = 1.0
