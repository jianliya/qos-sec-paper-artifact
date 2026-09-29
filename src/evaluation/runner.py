from __future__ import annotations


def run_scenario(event_loop, jobs):
    for job in jobs:
        event_loop.submit_job(job)
    return event_loop.run_until_done()
