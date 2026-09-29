from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BackendModel:
    backend_id: str
    num_qubits: int
    queue_time: float = 0.0
    quality_score: float = 1.0
    utilization: float = 0.0
    properties: dict = field(default_factory=dict)
