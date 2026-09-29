from __future__ import annotations

from backends.backend_model import BackendModel
from core.decision import ObservableTrace, ScheduleDecision
from core.job import Job
from estimator.quality_estimator import QualityEstimator
from scheduler.base_scheduler import BaseScheduler
from workloads.compile_aware import get_backend_compile_features


class BalancedScheduler(BaseScheduler):
    def __init__(self, alpha: float = 0.6, beta: float = 0.3, gamma: float = 0.1):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.qual_est = QualityEstimator()

    def _score(self, job: Job, backend: BackendModel) -> float:
        quality = self.qual_est.estimate(job, backend)
        wait_penalty = self._estimated_wait(job, backend)
        util_bonus = backend.utilization
        compile_feats = get_backend_compile_features(job, backend)
        suitability_bonus = 0.12 * float(compile_feats.get('backend_suitability', 0.0))
        return self.alpha * quality - self.beta * wait_penalty + self.gamma * util_bonus + suitability_bonus

    def _estimated_wait(self, job: Job, backend: BackendModel) -> float:
        compile_feats = get_backend_compile_features(job, backend)
        transpilation_penalty = float(getattr(backend, "properties", {}).get("transpilation_penalty", 1.0) or 1.0)
        noise_scale = float(getattr(backend, "properties", {}).get("noise_scale", 0.0) or 0.0)
        compile_delay = 0.18 * float(compile_feats.get('compile_cost', 0.0)) * transpilation_penalty
        swap_delay = 0.05 * float(compile_feats.get('swap_count', 0.0))
        depth_delay = 0.002 * float(compile_feats.get('compiled_depth', 0.0))
        noise_delay = 0.08 * noise_scale + 0.04 * float(compile_feats.get('noise_sensitivity', 0.0))
        return float(backend.queue_time) + compile_delay + swap_delay + depth_delay + noise_delay

    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        scored = sorted(((b, self._score(job, b)) for b in backends), key=lambda x: x[1], reverse=True)
        backend, best_score = scored[0]
        second_score = scored[1][1] if len(scored) > 1 else best_score
        wait = self._estimated_wait(job, backend)
        quality = self.qual_est.estimate(job, backend)
        start = job.submit_time + wait
        compile_feats = get_backend_compile_features(job, backend)
        trace = ObservableTrace(
            estimated_wait=wait,
            backend_id=backend.backend_id,
            queue_length=int(backend.queue_time),
            extra={
                'best_score': best_score,
                'score_margin': best_score - second_score,
                'compiled_depth': float(compile_feats.get('compiled_depth', 0.0)),
                'cx_count': float(compile_feats.get('cx_count', 0.0)),
                'swap_count': float(compile_feats.get('swap_count', 0.0)),
                'layout_span': float(compile_feats.get('layout_span', 0.0)),
                'expected_fidelity': float(compile_feats.get('expected_fidelity', quality)),
                'backend_suitability': float(compile_feats.get('backend_suitability', 0.0)),
            },
        )
        return ScheduleDecision(job_id=job.job_id, backend_id=backend.backend_id, start_time=start, estimated_wait=wait, estimated_quality=quality, observable=trace)
