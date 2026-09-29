from __future__ import annotations


class BaseOrchestrator:
    name = "base"

    def pick(self, jobs, backends, state):
        raise NotImplementedError
