from __future__ import annotations


def hardware_observation(record, defense_mode: str = 'full') -> dict:
    latency = float(record.latency)
    if defense_mode == 'hardened':
        return {
            'observed_wait': round(latency, 1),
            'queue_length': 0,
            'backend_id': 'masked',
            'score_margin': 0.0,
        }
    return {
        'observed_wait': round(latency, 4),
        'queue_length': 0,
        'backend_id': record.backend_id,
    }
