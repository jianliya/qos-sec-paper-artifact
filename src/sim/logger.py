from __future__ import annotations

from sim.state import BackendSnapshot


def backend_snapshots(backends) -> list[BackendSnapshot]:
    return [
        BackendSnapshot(
            backend_id=b.backend_id,
            queue_time=round(float(b.queue_time), 4),
            utilization=round(float(b.utilization), 4),
            quality_score=round(float(b.quality_score), 4),
        )
        for b in backends
    ]
