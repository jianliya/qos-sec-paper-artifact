from __future__ import annotations

import json

from scenarios.legacy_timing_leakage import run_multiseed, run_once


def run_timing_inference_case(seed: int = 42) -> dict:
    from pathlib import Path
    import json as _json
    cfg = _json.loads((Path(__file__).resolve().parents[2] / 'configs' / 'timing.json').read_text(encoding='utf-8'))
    return run_once(seed, cfg)


def run_timing_inference_multiseed(seeds: list[int] | None = None) -> dict:
    from pathlib import Path
    import json as _json
    cfg = _json.loads((Path(__file__).resolve().parents[2] / 'configs' / 'timing.json').read_text(encoding='utf-8'))
    if seeds is not None:
        cfg['seeds'] = seeds
    return run_multiseed(cfg)


if __name__ == '__main__':
    print(json.dumps(run_timing_inference_multiseed(), indent=2))
