from __future__ import annotations

from workloads.cloud_trace_sampler import sample_jobs_from_profile
from workloads.generators import make_job


def build_parameterized_contention_scenario(
    pressure_level: str = 'medium',
    victim_ratio: float = 0.2,
    scarce_backend_ratio: float = 0.5,
    mode: str = 'single',
    profile_name: str | None = None,
    num_jobs: int | None = None,
    num_tenants: int | None = None,
    seed: int = 42,
):
    if profile_name is not None:
        return sample_jobs_from_profile(
            num_jobs=num_jobs or 100,
            num_tenants=num_tenants or 4,
            profile_name=profile_name,
            seed=seed,
        )

    pressure_map = {
        'light': (2048, 120),
        'medium': (4096, 220),
        'heavy': (8192, 320),
    }
    shots, depth = pressure_map[pressure_level]

    victim_count = 2 if victim_ratio >= 0.3 else 1
    scarce_only = ['b1'] if scarce_backend_ratio >= 0.5 else ['b1', 'b2']

    jobs = [
        make_job('p1', 'tenantA', 0.0, ['b1', 'b2'], workload_role='benign', execution_mode=mode, shots=1024, depth_proxy=80),
        make_job('p2', 'tenantB', 0.2, scarce_only, workload_role='adversarial', execution_mode=mode, shots=shots, depth_proxy=depth),
        make_job('p3', 'tenantB', 0.4, scarce_only, workload_role='heavy', execution_mode=mode, shots=shots, depth_proxy=depth + 20),
    ]
    for i in range(victim_count):
        jobs.append(
            make_job(
                f'pv{i+1}',
                f'tenantV{i+1}',
                0.6 + i * 0.1,
                ['b1'],
                workload_role='benign',
                sensitivity='sensitive',
                execution_mode=mode,
                shots=1024,
                depth_proxy=120,
            )
        )
    return jobs
