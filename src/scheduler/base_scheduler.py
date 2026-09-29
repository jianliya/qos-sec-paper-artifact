from __future__ import annotations

from abc import ABC, abstractmethod

from core.job import Job
from core.decision import ScheduleDecision
from backends.backend_model import BackendModel


class BaseScheduler(ABC):
    @abstractmethod
    def schedule(self, job: Job, backends: list[BackendModel]) -> ScheduleDecision:
        raise NotImplementedError
