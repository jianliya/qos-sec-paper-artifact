from __future__ import annotations

from workloads.generators import make_job


def build_scenario():
    jobs = [
        make_job("m1", "tenantA", 0.0, ["b1", "b2"], workload_role="benign", sensitivity="normal"),
        make_job("m2", "tenantV1", 0.3, ["b1"], workload_role="benign", sensitivity="sensitive", depth_proxy=140),
        make_job("m3", "tenantV2", 0.4, ["b2"], workload_role="benign", sensitivity="sensitive", depth_proxy=130),
        make_job("m4", "tenantB", 0.5, ["b1", "b2"], workload_role="heavy", shots=3072, depth_proxy=210),
        make_job("m5", "tenantC", 0.7, ["b2"], workload_role="heavy", shots=2048, depth_proxy=160),
    ]
    return jobs
