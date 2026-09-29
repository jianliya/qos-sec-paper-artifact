from __future__ import annotations

import random
from dataclasses import dataclass

from backends.qiskit_fake_backends import load_ibm_fake_backends
from scheduler.baseline_scheduler import BaselineScheduler
from scheduler.balanced_scheduler import BalancedScheduler
from scheduler.contention_robust import ContentionRobustOrchestrator
from scheduler.contention_robust_ext import ContentionRobustExtOrchestrator
from scheduler.fifo_eligibility import FIFOEligibilityOrchestrator
from scheduler.fcfs_visible import FCFSVisibleOrchestrator
from scheduler.isolation_scheduler import IsolationScheduler
from scheduler.jct_oriented import JCTOrientedOrchestrator
from scheduler.latency_noise_aware import LatencyNoiseAwareOrchestrator
from scheduler.legacy_secure_joint import SecureJointFeatures, SecureJointScheduler
from scheduler.naive_isolation import NaiveIsolationOrchestrator
from scheduler.partition_fidelity_aware import PartitionFidelityAwareOrchestrator
from scheduler.quota_scheduler import QuotaScheduler
from scheduler.quality_first_scheduler import QualityFirstScheduler
from scheduler.randomized_backend_visible import RandomizedBackendVisibleOrchestrator
from scheduler.randomized_backend_scheduler import RandomizedBackendScheduler
from scheduler.strict_isolation_quota import StrictIsolationQuotaOrchestrator


@dataclass
class V2Backend:
    backend_id: str
    qubit_capacity: int
    connectivity_proxy: str
    fidelity_proxy: float
    base_service_rate: float
    supports_modes: list[str]
    transpilation_penalty_profile: dict
    scarcity_score: float = 0.0


def clone_backends(rng: random.Random, backend_profile: dict | None = None):
    profile = backend_profile or {}
    use_backend_quality_variation = profile.get('use_backend_quality_variation', True)
    use_queue_time_variation = profile.get('use_queue_time_variation', True)
    use_backend_utilization_variation = profile.get('use_backend_utilization_variation', True)
    use_backend_size_heterogeneity = profile.get('use_backend_size_heterogeneity', True)
    use_compile_path_variation = profile.get('use_compile_path_variation', True)
    use_noise_shaping_variation = profile.get('use_noise_shaping_variation', True)
    noise_profile_mode = profile.get('noise_profile_mode', 'default')
    heterogeneity_intensity = float(profile.get('heterogeneity_intensity', 1.0))
    heterogeneity_intensity = min(1.0, max(0.0, heterogeneity_intensity))
    clones = []
    source_backends = load_ibm_fake_backends()
    if use_backend_quality_variation:
        quality_values = [b.quality_score for b in source_backends]
        quality_anchor = sum(quality_values) / max(len(quality_values), 1)
    else:
        quality_values = [b.quality_score for b in source_backends]
        quality_anchor = sum(quality_values) / max(len(quality_values), 1)
    if use_backend_size_heterogeneity:
        size_anchor = None
    else:
        size_values = [b.num_qubits for b in source_backends]
        size_anchor = int(round(sum(size_values) / max(len(size_values), 1)))
    noise_anchor = sum(max(0.0, 1.0 - float(b.quality_score)) for b in source_backends) / max(len(source_backends), 1)
    if noise_profile_mode == 'uniform':
        quality_variation_scale = 0.01
        noise_extra_scale = 0.01
        drift_strength = 0.0
    elif noise_profile_mode == 'moderate':
        quality_variation_scale = 0.045
        noise_extra_scale = 0.05
        drift_strength = 0.01
    elif noise_profile_mode == 'high_drift':
        quality_variation_scale = 0.085
        noise_extra_scale = 0.12
        drift_strength = 0.03
    else:
        quality_variation_scale = 0.03
        noise_extra_scale = 0.08
        drift_strength = 0.0
    for b in source_backends:
        props = dict(b.properties)
        props.pop('backend_obj', None)
        queue_time = b.queue_time
        if use_queue_time_variation:
            queue_time = max(0.15, queue_time + heterogeneity_intensity * rng.uniform(-0.25, 0.25))
        utilization = b.utilization
        if use_backend_utilization_variation:
            utilization = min(0.95, max(0.01, utilization + heterogeneity_intensity * rng.uniform(-0.04, 0.04)))
        if use_backend_quality_variation:
            quality_score = min(
                0.99,
                max(
                    0.5,
                    b.quality_score + heterogeneity_intensity * rng.uniform(-quality_variation_scale, quality_variation_scale),
                ),
            )
        else:
            quality_score = quality_anchor
        if size_anchor is None:
            size_values = [backend.num_qubits for backend in source_backends]
            size_mean = sum(size_values) / max(len(size_values), 1)
            num_qubits = int(round(size_mean + heterogeneity_intensity * (b.num_qubits - size_mean)))
        else:
            num_qubits = size_anchor
        if use_compile_path_variation:
            transpilation_penalty = max(
                0.75,
                1.0 + 0.35 * heterogeneity_intensity * ((float(num_qubits) - 15.0) / 15.0) + rng.uniform(-0.08, 0.08),
            )
        else:
            transpilation_penalty = 1.0
        if use_noise_shaping_variation:
            noise_scale = max(
                0.0,
                (1.0 - quality_score) + 0.12 * float(utilization) + noise_extra_scale * heterogeneity_intensity * rng.uniform(-1.0, 1.0),
            )
            crosstalk_risk = max(
                0.0,
                0.18 * float(utilization) + 0.04 * float(queue_time) + (0.02 + noise_extra_scale / 2.0) * heterogeneity_intensity * rng.uniform(0.0, 1.0),
            )
        else:
            noise_scale = 0.0
            crosstalk_risk = 0.0
        props['transpilation_penalty'] = round(float(transpilation_penalty), 4)
        props['noise_scale'] = round(float(noise_scale), 4)
        props['crosstalk_risk'] = round(float(crosstalk_risk), 4)
        props['noise_profile_mode'] = noise_profile_mode
        props['noise_drift_strength'] = round(float(drift_strength * heterogeneity_intensity), 4)
        props['noise_anchor'] = round(float(noise_anchor), 4)
        clones.append(type(b)(
            backend_id=b.backend_id,
            num_qubits=num_qubits,
            queue_time=queue_time,
            quality_score=quality_score,
            utilization=utilization,
            properties=props,
        ))
    return clones


def build_v2_backends(seed: int = 42):
    rng = random.Random(seed)
    return [
        V2Backend(
            backend_id='b1',
            qubit_capacity=27,
            connectivity_proxy='grid',
            fidelity_proxy=0.95,
            base_service_rate=1.0,
            supports_modes=['single', 'session', 'batch'],
            transpilation_penalty_profile={'default': 1.0},
            scarcity_score=0.3 + rng.uniform(0.0, 0.2),
        ),
        V2Backend(
            backend_id='b2',
            qubit_capacity=65,
            connectivity_proxy='heavy_hex',
            fidelity_proxy=0.92,
            base_service_rate=1.2,
            supports_modes=['single', 'session', 'batch'],
            transpilation_penalty_profile={'default': 0.8},
            scarcity_score=0.1 + rng.uniform(0.0, 0.1),
        ),
    ]


def build_scheduler(name: str):
    if name == 'queue':
        return BaselineScheduler()
    if name == 'balanced':
        return BalancedScheduler()
    if name == 'quota':
        return QuotaScheduler({'attacker': 0.6, 'victim': 1.2, 'benign': 1.0})
    if name == 'isolation':
        return IsolationScheduler()
    if name == 'quality_first':
        return QualityFirstScheduler()
    if name == 'randomized_backend':
        return RandomizedBackendScheduler()
    if name == 'secure_joint':
        return SecureJointScheduler()
    if name == 'secure_joint_no_risk':
        return SecureJointScheduler(features=SecureJointFeatures(enable_risk=False))
    if name == 'secure_joint_no_leakage':
        return SecureJointScheduler(features=SecureJointFeatures(enable_leakage=False))
    if name == 'secure_joint_no_quota':
        return SecureJointScheduler(features=SecureJointFeatures(enable_quota=False))
    if name == 'secure_joint_no_victim_bias':
        return SecureJointScheduler(features=SecureJointFeatures(enable_victim_bias=False))
    if name == 'secure_joint_no_isolation':
        return SecureJointScheduler(features=SecureJointFeatures(enable_isolation_guard=False))
    if name == 'fifo_eligibility':
        return FIFOEligibilityOrchestrator()
    if name == 'fcfs_visible':
        return FCFSVisibleOrchestrator()
    if name == 'latency_noise_aware':
        return LatencyNoiseAwareOrchestrator()
    if name == 'jct_oriented':
        return JCTOrientedOrchestrator()
    if name == 'partition_fidelity_aware':
        return PartitionFidelityAwareOrchestrator()
    if name == 'randomized_backend_visible':
        return RandomizedBackendVisibleOrchestrator()
    if name == 'naive_isolation':
        return NaiveIsolationOrchestrator()
    if name == 'strict_isolation_quota':
        return StrictIsolationQuotaOrchestrator()
    if name == 'contention_robust_ext':
        return ContentionRobustExtOrchestrator()
    if name == 'contention_robust':
        return ContentionRobustOrchestrator()
    raise ValueError(f'unknown scheduler: {name}')
