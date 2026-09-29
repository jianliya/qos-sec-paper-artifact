from __future__ import annotations

import random

from core.decision import ObservableTrace


def apply_observability(trace: ObservableTrace | None, mode: str = "full", rng: random.Random | None = None) -> dict:
    if trace is None:
        return {}
    rng = rng or random
    extra = dict(trace.extra or {})
    observed_wait = float(trace.estimated_wait)
    if mode == "masked":
        return {
            "observed_wait": round(observed_wait, 3),
            "queue_length": 0,
            "backend_id": "masked",
        }
    if mode == "external_only":
        return {
            "observed_wait": round(observed_wait, 4),
            "backend_id": trace.backend_id,
        }
    if mode == "scheduler_boundary":
        return {
            "observed_wait": round(observed_wait, 4),
            "queue_length": int(trace.queue_length),
            "backend_id": trace.backend_id,
            **{k: round(v, 4) if isinstance(v, float) else v for k, v in extra.items()},
        }
    if mode == "coarse":
        return {
            "observed_wait": round(observed_wait, 3),
            "queue_length": int(trace.queue_length // 2),
            "backend_id": trace.backend_id,
            "score_margin": round(float(extra.get("score_margin", 0.0)), 2),
        }
    if mode == "masked_backend_only":
        return {
            "observed_wait": round(observed_wait, 4),
            "queue_length": int(trace.queue_length),
            "backend_id": "masked",
            **{
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in extra.items()
            },
        }
    if mode == "queue_length_only":
        return {
            "observed_wait": 0.0,
            "queue_length": int(trace.queue_length),
            "backend_id": "masked",
            "score_margin": 0.0,
        }
    if mode == "jittered":
        jitter = rng.uniform(-0.15, 0.15)
        bucketed_wait = round(max(0.0, observed_wait + jitter), 1)
        return {
            "observed_wait": bucketed_wait,
            "queue_length": int(trace.queue_length // 3),
            "backend_id": "masked",
            "score_margin": round(float(extra.get("score_margin", 0.0)), 1),
        }
    if mode == "hardened":
        jitter = rng.uniform(-0.35, 0.35)
        bucketed_wait = round(max(0.0, observed_wait + jitter), 1)
        return {
            "observed_wait": bucketed_wait,
            "queue_length": 0,
            "backend_id": "masked",
            "score_margin": 0.0,
        }
    return {
        "observed_wait": round(observed_wait, 4),
        "queue_length": int(trace.queue_length),
        "backend_id": trace.backend_id,
        **{k: round(v, 4) if isinstance(v, float) else v for k, v in extra.items()},
    }
