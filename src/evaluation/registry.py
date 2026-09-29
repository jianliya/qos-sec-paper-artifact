from __future__ import annotations

from scheduler.contention_robust_ext import ContentionRobustExtOrchestrator
from scheduler.fifo_eligibility import FIFOEligibilityOrchestrator
from scheduler.latency_noise_aware import LatencyNoiseAwareOrchestrator
from scheduler.partition_fidelity_aware import PartitionFidelityAwareOrchestrator
from scheduler.strict_isolation_quota import StrictIsolationQuotaOrchestrator


SCHEDULER_REGISTRY = {
    'fifo_eligibility': FIFOEligibilityOrchestrator,
    'latency_noise_aware': LatencyNoiseAwareOrchestrator,
    'partition_fidelity_aware': PartitionFidelityAwareOrchestrator,
    'strict_isolation_quota': StrictIsolationQuotaOrchestrator,
    'contention_robust_ext': ContentionRobustExtOrchestrator,
}
