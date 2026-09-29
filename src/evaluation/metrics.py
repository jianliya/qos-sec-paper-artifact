from __future__ import annotations

from statistics import mean


def safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, int(round((len(vals) - 1) * p))))
    return float(vals[idx])


def victim_degradation_ratio(baseline_wait: float, compared_wait: float) -> float:
    if baseline_wait <= 1e-9:
        return 0.0
    return float((compared_wait - baseline_wait) / baseline_wait)
