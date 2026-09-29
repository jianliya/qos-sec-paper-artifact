from __future__ import annotations

from workloads.generators import make_job


def build_scenario():
    jobs = [
        make_job("j1", "tenantA", 0.0, ["b1"], workload_role="benign"),
        make_job("j2", "tenantB", 0.5, ["b1"], workload_role="heavy", shots=2048, depth_proxy=150),
        make_job("j3", "tenantV", 1.0, ["b1"], workload_role="benign", sensitivity="sensitive", depth_proxy=120),
    ]
    return jobs
