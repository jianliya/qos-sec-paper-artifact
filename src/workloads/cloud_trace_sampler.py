from __future__ import annotations

import random

from workloads.generators import make_job
from workloads.ravi_profile import PROFILES, RAVI_BASELINE, RaviWorkloadProfile


def _weighted_choice(rng: random.Random, values: tuple[int, ...], weights: tuple[float, ...]) -> int:
    total = sum(weights)
    pivot = rng.random() * total
    acc = 0.0
    for value, weight in zip(values, weights):
        acc += weight
        if pivot <= acc:
            return value
    return values[-1]


def _profile_from_name(name: str | None) -> RaviWorkloadProfile:
    if not name:
        return RAVI_BASELINE
    return PROFILES.get(name, RAVI_BASELINE)


def sample_jobs_from_profile(
    num_jobs: int = 100,
    num_tenants: int = 4,
    profile_name: str | None = None,
    seed: int = 42,
):
    rng = random.Random(seed)
    profile = _profile_from_name(profile_name)
    jobs = []
    now = 0.0
    backend_ids = ["b1", "b2"]
    for idx in range(num_jobs):
        tenant_idx = idx % max(num_tenants, 1)
        tenant_id = f"tenant{tenant_idx}"
        workload_role = "adversarial" if rng.random() < profile.attacker_share else "benign"
        sensitivity = "sensitive" if rng.random() < profile.sensitive_share else "normal"
        scarcity_only = rng.random() < profile.backend_scarcity_share
        eligibility = ["b1"] if scarcity_only else list(backend_ids)
        shots = _weighted_choice(rng, profile.shot_buckets, profile.shot_weights)
        depth = _weighted_choice(rng, profile.depth_buckets, profile.depth_weights)
        logical_qubits = 8 if scarcity_only else (12 if shots >= 4096 else 6)
        execution_mode = "session" if rng.random() < 0.25 else "single"
        job = make_job(
            job_id=f"trace_{idx}",
            tenant_id=tenant_id,
            submit_time=round(now, 4),
            backend_eligibility=eligibility,
            execution_mode=execution_mode,
            shots=shots,
            logical_qubits=logical_qubits,
            depth_proxy=depth,
            two_qubit_gate_proxy=max(10, depth // 4),
            sensitivity=sensitivity,
            workload_role=workload_role,
        )
        job.metadata.workload_tag = profile.name
        job.metadata.declared_demand = max(1, logical_qubits // 2)
        job.metadata.estimated_runtime = float(shots) / 1024.0 + float(depth) / 100.0
        if sensitivity == "sensitive":
            job.metadata.isolation_level = "high"
        jobs.append(job)
        now += rng.expovariate(1.0 / max(profile.interarrival_scale, 0.05))
    return jobs
