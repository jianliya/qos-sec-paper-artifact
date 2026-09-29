from __future__ import annotations

import math
import random
from statistics import mean, pstdev, stdev


_T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.16,
    14: 2.145,
    15: 2.131,
    16: 2.12,
    17: 2.11,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.08,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.06,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _t_critical_95(df: int) -> float:
    if df <= 0:
        return 0.0
    if df in _T_CRITICAL_95:
        return _T_CRITICAL_95[df]
    if df < 60:
        return 2.0
    return 1.96


def _bootstrap_interval(values: list[float], iterations: int = 2000, seed: int = 0) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    samples = []
    n = len(values)
    for _ in range(max(1, iterations)):
        draws = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(mean(draws))
    samples.sort()
    lo_idx = max(0, int(0.025 * (len(samples) - 1)))
    hi_idx = min(len(samples) - 1, int(0.975 * (len(samples) - 1)))
    return float(samples[lo_idx]), float(samples[hi_idx])


def summarize(
    values: list[float],
    ci_method: str = "normal",
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 0,
) -> dict:
    if not values:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "ci95": 0.0,
            "ci95_low": 0.0,
            "ci95_high": 0.0,
            "ci_method": ci_method,
        }
    mu = mean(values)
    sd = pstdev(values)
    ci_method = ci_method or "normal"
    if len(values) == 1:
        lo = hi = float(values[0])
    elif ci_method == "bootstrap":
        lo, hi = _bootstrap_interval(values, iterations=bootstrap_iterations, seed=bootstrap_seed)
    elif ci_method == "student_t":
        sample_sd = stdev(values)
        half = _t_critical_95(len(values) - 1) * sample_sd / math.sqrt(len(values))
        lo, hi = float(mu - half), float(mu + half)
    else:
        half = 1.96 * sd / math.sqrt(len(values))
        lo, hi = float(mu - half), float(mu + half)
    ci95 = max(0.0, (hi - lo) / 2.0)
    return {
        "mean": round(float(mu), 4),
        "std": round(float(sd), 4),
        "min": round(float(min(values)), 4),
        "max": round(float(max(values)), 4),
        "ci95": round(float(ci95), 4),
        "ci95_low": round(float(lo), 4),
        "ci95_high": round(float(hi), 4),
        "ci_method": ci_method,
    }
