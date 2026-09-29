from __future__ import annotations

from scheduler.fcfs_visible import FCFSVisibleOrchestrator


class FIFOEligibilityOrchestrator(FCFSVisibleOrchestrator):
    name = "fifo_eligibility"
