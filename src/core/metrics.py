from __future__ import annotations


def queue_wait(lifecycle):
    if lifecycle.queued_at is None or lifecycle.running_at is None:
        return None
    return lifecycle.running_at - lifecycle.queued_at


def turnaround_time(lifecycle):
    if lifecycle.created_at is None or lifecycle.finished_at is None:
        return None
    return lifecycle.finished_at - lifecycle.created_at


from statistics import mean


def victim_wait_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def blocked_ratio(total: int, blocked: int) -> float:
    return blocked / total if total else 0.0


def leakage_advantage(accuracy: float, prior: float = 0.5) -> float:
    return accuracy - prior
