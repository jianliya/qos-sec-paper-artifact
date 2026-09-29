from __future__ import annotations

from workloads.generators import make_job


def build_scenario():
    jobs = [
        make_job("s1", "tenantA", 0.0, ["b1", "b2"], workload_role="benign"),
        make_job("s2", "tenantB", 0.2, ["b1"], workload_role="heavy", shots=4096, depth_proxy=200),
        make_job("s3", "tenantV", 0.3, ["b1"], workload_role="benign", sensitivity="sensitive", shots=1024, depth_proxy=120),
        make_job("s4", "tenantC", 0.5, ["b2"], workload_role="benign", shots=2048, depth_proxy=110),
    ]
    return jobs
