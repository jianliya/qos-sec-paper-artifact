from __future__ import annotations

from dataclasses import dataclass

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from estimator.risk_estimator import RiskEstimator
from scheduler.base_scheduler import BaseScheduler
from workloads.compile_aware import get_backend_compile_features


@dataclass
class SecureJointFeatures:
    enable_risk: bool = True
    enable_leakage: bool = True
    enable_quota: bool = True
    enable_victim_bias: bool = True
    enable_isolation_guard: bool = True


class SecureJointScheduler(BaseScheduler):
    def __init__(
        self,
        alpha: float = 0.7,
        beta: float = 0.35,
        gamma: float = 0.5,
        delta: float = 0.4,
        tenant_quota: dict[str, float] | None = None,
        features: SecureJointFeatures | None = None,
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta
        self.tenant_quota = tenant_quota or {'attacker': 0.45, 'victim': 1.2, 'benign': 1.0}
        self.features = features or SecureJointFeatures()
        self.qual_est = QualityEstimator()
        self.risk_est = RiskEstimator()

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        job_risk = self.risk_est.exhaustion_risk(job)
        job_leak = self.risk_est.timing_leakage_risk(job)
        quota = self.tenant_quota.get(job.tenant_id, 1.0) if self.features.enable_quota else 1.0
        scored = []
        for backend in backends:
            quality = self.qual_est.estimate(job, backend)
            compile_feats = get_backend_compile_features(job, backend)
            transpilation_penalty = float(getattr(backend, "properties", {}).get("transpilation_penalty", 1.0) or 1.0)
            noise_scale = float(getattr(backend, "properties", {}).get("noise_scale", 0.0) or 0.0)
            crosstalk_risk = float(getattr(backend, "properties", {}).get("crosstalk_risk", 0.0) or 0.0)
            compile_delay = 0.16 * float(compile_feats.get('compile_cost', 0.0)) * transpilation_penalty
            routing_delay = 0.04 * float(compile_feats.get('swap_count', 0.0)) + 0.002 * float(compile_feats.get('compiled_depth', 0.0))
            noise_delay = 0.06 * noise_scale + 0.04 * crosstalk_risk + 0.03 * float(compile_feats.get('noise_sensitivity', 0.0))
            effective_wait = (float(backend.queue_time) + compile_delay + noise_delay) / max(quota, 0.1)
            effective_wait += routing_delay
            if self.features.enable_isolation_guard and job.metadata.isolation_level == 'high' and backend.num_qubits < max(job.num_qubits() + 2, 12):
                effective_wait += 1.0
            backend_risk = self.risk_est.backend_exhaustion_risk(job, backend) if self.features.enable_risk else 0.0
            backend_leak = self.risk_est.backend_timing_leakage_risk(job, backend) if self.features.enable_leakage else 0.0
            suitability_bonus = 0.18 * float(compile_feats.get('backend_suitability', 0.0))
            score = self.alpha * quality - self.beta * effective_wait - self.gamma * backend_risk - self.delta * backend_leak + 0.1 * backend.utilization + suitability_bonus
            if self.features.enable_victim_bias and job.tenant_id == 'victim':
                score += 0.15
            scored.append((backend, score, quality, effective_wait, backend_risk, backend_leak, compile_feats))
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)
        backend, best_score, quality, wait, best_backend_risk, best_backend_leak, best_compile_feats = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else best_score
        accepted = True
        reason = 'scheduled'
        if self.features.enable_risk and job.tenant_id == 'attacker' and best_backend_risk > 0.8 and wait > 1.5:
            accepted = False
            reason = 'risk_throttled'
        trace = ObservableTrace(
            estimated_wait=wait,
            backend_id=backend.backend_id,
            queue_length=int(backend.queue_time),
            extra={
                "job_risk": job_risk,
                "job_leakage": job_leak,
                "backend_risk": best_backend_risk,
                "backend_leakage": best_backend_leak,
                "quota": quota,
                "best_score": best_score,
                "score_margin": best_score - second_score,
                "compiled_depth": float(best_compile_feats.get('compiled_depth', 0.0)),
                "cx_count": float(best_compile_feats.get('cx_count', 0.0)),
                "swap_count": float(best_compile_feats.get('swap_count', 0.0)),
                "layout_span": float(best_compile_feats.get('layout_span', 0.0)),
                "expected_fidelity": float(best_compile_feats.get('expected_fidelity', quality)),
                "backend_suitability": float(best_compile_feats.get('backend_suitability', 0.0)),
                "features": {
                    "risk": self.features.enable_risk,
                    "leakage": self.features.enable_leakage,
                    "quota": self.features.enable_quota,
                    "victim_bias": self.features.enable_victim_bias,
                    "isolation_guard": self.features.enable_isolation_guard,
                },
            },
        )
        return ScheduleDecision(
            job_id=job.job_id,
            backend_id=backend.backend_id,
            start_time=job.submit_time + wait,
            estimated_wait=wait,
            estimated_quality=quality,
            accepted=accepted,
            reason=reason,
            observable=trace,
        )
