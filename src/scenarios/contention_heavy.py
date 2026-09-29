from __future__ import annotations

from workloads.generators import make_job


def build_scenario():
    jobs = [
        make_job("h1", "tenantA", 0.0, ["b1", "b2"], workload_role="benign", shots=1024, depth_proxy=80),
        make_job("h2", "tenantB", 0.2, ["b1"], workload_role="heavy", shots=4096, depth_proxy=220),
        make_job("h3", "tenantB", 0.4, ["b1"], workload_role="heavy", shots=4096, depth_proxy=240),
        make_job("h4", "tenantV", 0.6, ["b1"], workload_role="benign", sensitivity="sensitive", shots=1024, depth_proxy=100),
        make_job("h5", "tenantB", 0.8, ["b1"], workload_role="adversarial", shots=8192, depth_proxy=260),
    ]
    return jobs
