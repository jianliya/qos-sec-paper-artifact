from __future__ import annotations

from core.job import Job
from backends.backend_model import BackendModel
from estimator.compatibility import CompatibilityEstimator


class Bundler:
    def __init__(self, compatibility: CompatibilityEstimator | None = None, threshold: float = 0.5):
        self.compatibility = compatibility or CompatibilityEstimator()
        self.threshold = threshold

    def can_colocate(self, job_a: Job, job_b: Job, backend: BackendModel) -> bool:
        return self.compatibility.score(job_a, job_b, backend) >= self.threshold
