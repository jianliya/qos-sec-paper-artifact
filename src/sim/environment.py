from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from core.job import Job
from sim.logger import backend_snapshots
from sim.observability import apply_observability
from sim.state import SimulationRecord


@dataclass
class SimulationEnvironment:
    backends: list
    scheduler: object
    rng: random.Random
    observability_mode: str = "full"
    defense_profile: dict = field(default_factory=dict)
    records: list[SimulationRecord] = field(default_factory=list)
    backend_history: list[dict] = field(default_factory=list)
    defense_state: dict = field(default_factory=dict)

    def step(self, job: Job, pressure: float = 0.0, accept_override: tuple[bool, str] | None = None) -> SimulationRecord:
        decision = self.scheduler.schedule(job, self.backends)
        if accept_override is not None:
            decision.accepted, decision.reason = accept_override
        if decision.accepted:
            self._apply_pressure(decision.backend_id, pressure)
        observed = apply_observability(decision.observable, self.observability_mode, self.rng)
        observed = self._apply_timing_defense(job, observed)
        record = SimulationRecord(
            job_id=decision.job_id,
            tenant_id=job.tenant_id,
            workload_tag=job.metadata.workload_tag,
            backend_id=decision.backend_id,
            accepted=decision.accepted,
            reason=decision.reason,
            estimated_wait=round(float(decision.estimated_wait), 4),
            estimated_quality=round(float(decision.estimated_quality), 4),
            observed=observed,
        )
        self.records.append(record)
        self.backend_history.append({"job_id": job.job_id, "snapshots": [s.__dict__ for s in backend_snapshots(self.backends)]})
        return record

    def _apply_timing_defense(self, job: Job, observed: dict) -> dict:
        if not observed:
            return observed
        mode = self.observability_mode
        if mode not in {"jittered", "hardened"}:
            return observed

        defended = dict(observed)
        wait = float(defended.get('observed_wait', 0.0))
        running_mean = float(self.defense_state.get('running_probe_wait_mean', wait))
        profile = {
            'padding': self.defense_profile.get('padding', True),
            'mask_backend': self.defense_profile.get('mask_backend', True),
            'reset_queue': self.defense_profile.get('reset_queue', True),
            'suppress_score': self.defense_profile.get('suppress_score', True),
            'cover_target': float(self.defense_profile.get('cover_target', 0.45)),
            'cover_noise': float(self.defense_profile.get('cover_noise', 0.18)),
            'release_rule': str(self.defense_profile.get('release_rule', 'legacy_cover')),
            'bucket_width': float(self.defense_profile.get('bucket_width', 0.2)),
            'release_noise': float(self.defense_profile.get('release_noise', 0.0)),
            'apply_scope': str(self.defense_profile.get('apply_scope', 'probe_only')),
        }

        def _shape_release_wait(raw_wait: float, pressure_proxy: float) -> float:
            if mode == 'jittered':
                mixed = 0.55 * raw_wait + 0.45 * running_mean + self.rng.uniform(-0.10, 0.10)
                return round(max(0.0, mixed), 1)
            if not profile['padding']:
                fallback = 0.65 * raw_wait + 0.35 * pressure_proxy + self.rng.uniform(-0.12, 0.12)
                return round(max(0.0, fallback), 1)

            release_rule = profile['release_rule']
            cover_target = profile['cover_target']
            cover_noise = profile['cover_noise']
            release_noise = max(0.0, profile['release_noise'])
            bucket_width = max(0.05, profile['bucket_width'])
            if release_rule == 'monotone_padding':
                padded = max(raw_wait, cover_target) + self.rng.uniform(0.0, release_noise)
                return round(max(0.0, padded), 1)
            if release_rule == 'delayed_release':
                bucketed = math.ceil(raw_wait / bucket_width) * bucket_width
                padded = bucketed + self.rng.uniform(0.0, release_noise)
                return round(max(0.0, padded), 1)
            padded = cover_target + self.rng.uniform(-cover_noise, cover_noise)
            return round(max(0.0, padded), 1)

        apply_scope = profile['apply_scope']
        apply_release = apply_scope == 'all' or job.metadata.workload_tag == 'probe'

        if job.metadata.workload_tag in {'classA', 'classB', 'highIsolation'}:
            victim_pressure = float(self.defense_state.get('victim_pressure', 0.0))
            victim_pressure = 0.65 * victim_pressure + 0.35 * wait
            if job.metadata.isolation_level == 'high':
                victim_pressure *= 0.92
            self.defense_state['victim_pressure'] = victim_pressure
            if apply_release and mode == 'hardened':
                defended['observed_wait'] = _shape_release_wait(wait, victim_pressure)
            return defended

        if job.metadata.workload_tag == 'probe':
            victim_pressure = float(self.defense_state.get('victim_pressure', running_mean))
            if mode == 'jittered':
                defended['observed_wait'] = _shape_release_wait(wait, victim_pressure)
                defended['queue_length'] = int(defended.get('queue_length', 0) // 2)
                if profile['mask_backend']:
                    defended['backend_id'] = 'masked'
            else:  # hardened
                defended['observed_wait'] = _shape_release_wait(wait, victim_pressure)
                if profile['reset_queue']:
                    defended['queue_length'] = 0
                if profile['mask_backend']:
                    defended['backend_id'] = 'masked'
                if profile['suppress_score']:
                    defended['score_margin'] = 0.0
            new_mean = 0.8 * running_mean + 0.2 * float(defended['observed_wait'])
            self.defense_state['running_probe_wait_mean'] = new_mean
            return defended

        if apply_release and mode == 'hardened':
            victim_pressure = float(self.defense_state.get('victim_pressure', running_mean))
            defended['observed_wait'] = _shape_release_wait(wait, victim_pressure)

        return defended

    def _apply_pressure(self, backend_id: str, pressure: float) -> None:
        for backend in self.backends:
            if backend.backend_id == backend_id:
                backend.queue_time = max(0.15, 0.72 * backend.queue_time + pressure)
                backend.utilization = min(1.0, 0.6 * backend.utilization + 0.4 * min(1.0, pressure / max(backend.num_qubits, 1)))
            else:
                backend.queue_time = max(0.15, backend.queue_time * 0.84)
                backend.utilization = max(0.02, backend.utilization * 0.8)
            drift_strength = float(getattr(backend, 'properties', {}).get('noise_drift_strength', 0.0) or 0.0)
            if drift_strength > 0.0:
                delta = self.rng.uniform(-drift_strength, drift_strength)
                backend.quality_score = min(0.99, max(0.5, float(backend.quality_score) + delta))
                noise_scale = float(getattr(backend, 'properties', {}).get('noise_scale', max(0.0, 1.0 - float(backend.quality_score))) or 0.0)
                crosstalk = float(getattr(backend, 'properties', {}).get('crosstalk_risk', 0.0) or 0.0)
                backend.properties['noise_scale'] = round(max(0.0, noise_scale - 0.55 * delta + self.rng.uniform(-0.01, 0.01)), 4)
                backend.properties['crosstalk_risk'] = round(max(0.0, crosstalk + 0.35 * abs(delta) + self.rng.uniform(-0.005, 0.005)), 4)
