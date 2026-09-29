from __future__ import annotations

from workloads.cloud_trace_sampler import sample_jobs_from_profile


def build_profiled_scenario(
    profile_name: str = 'ravi_baseline',
    num_jobs: int = 100,
    num_tenants: int = 4,
    seed: int = 42,
):
    return sample_jobs_from_profile(
        num_jobs=num_jobs,
        num_tenants=num_tenants,
        profile_name=profile_name,
        seed=seed,
    )


PROFILE_SCENARIOS = {
    'ravi_baseline_50x2': lambda: build_profiled_scenario('ravi_baseline', 50, 2, 41),
    'ravi_baseline_100x4': lambda: build_profiled_scenario('ravi_baseline', 100, 4, 42),
    'ravi_pressured_100x4': lambda: build_profiled_scenario('ravi_pressured', 100, 4, 43),
    'ravi_pressured_200x8': lambda: build_profiled_scenario('ravi_pressured', 200, 8, 44),
}
