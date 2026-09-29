from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RaviWorkloadProfile:
    name: str
    shot_buckets: tuple[int, ...]
    shot_weights: tuple[float, ...]
    depth_buckets: tuple[int, ...]
    depth_weights: tuple[float, ...]
    interarrival_scale: float
    attacker_share: float
    sensitive_share: float
    backend_scarcity_share: float


RAVI_BASELINE = RaviWorkloadProfile(
    name="ravi_baseline",
    shot_buckets=(256, 512, 1024, 2048, 4096, 8192),
    shot_weights=(0.08, 0.14, 0.30, 0.22, 0.16, 0.10),
    depth_buckets=(40, 80, 120, 180, 260),
    depth_weights=(0.10, 0.28, 0.30, 0.20, 0.12),
    interarrival_scale=0.65,
    attacker_share=0.20,
    sensitive_share=0.18,
    backend_scarcity_share=0.45,
)

RAVI_PRESSURED = RaviWorkloadProfile(
    name="ravi_pressured",
    shot_buckets=(512, 1024, 2048, 4096, 8192, 16384),
    shot_weights=(0.06, 0.12, 0.24, 0.24, 0.20, 0.14),
    depth_buckets=(60, 100, 160, 240, 320),
    depth_weights=(0.08, 0.20, 0.30, 0.25, 0.17),
    interarrival_scale=0.45,
    attacker_share=0.28,
    sensitive_share=0.22,
    backend_scarcity_share=0.60,
)


PROFILES = {
    RAVI_BASELINE.name: RAVI_BASELINE,
    RAVI_PRESSURED.name: RAVI_PRESSURED,
}
