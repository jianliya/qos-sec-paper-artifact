from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class JobMetadata:
    workload_tag: str = "unknown"
    declared_demand: int = 1
    estimated_runtime: float | None = None
    isolation_level: str = "normal"
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    job_id: str
    tenant_id: str
    circuit: Any
    submit_time: float

    execution_mode: str = "single"
    shots: int = 1024
    logical_qubits: int = 0
    depth_proxy: float = 0.0
    two_qubit_gate_proxy: float = 0.0
    backend_eligibility: list[str] = field(default_factory=list)
    sensitivity: str = "normal"
    workload_role: str = "benign"
    session_id: Optional[str] = None
    batch_id: Optional[str] = None
    estimated_compile_cost: float = 0.0
    estimated_service_demand: float = 0.0

    priority: int = 0
    metadata: JobMetadata = field(default_factory=JobMetadata)
    tags: set[str] = field(default_factory=set)

    def num_qubits(self) -> int:
        if self.logical_qubits:
            return int(self.logical_qubits)
        if hasattr(self.circuit, "num_qubits"):
            return int(self.circuit.num_qubits)
        return int(self.metadata.notes.get("num_qubits", 0))

    def depth(self) -> int:
        if self.depth_proxy:
            return int(self.depth_proxy)
        if hasattr(self.circuit, "depth"):
            try:
                return int(self.circuit.depth())
            except TypeError:
                return int(self.circuit.depth)
        return int(self.metadata.notes.get("depth", 0))
