from __future__ import annotations

import csv
import json
from pathlib import Path


def export_json(result: dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')


def export_system_csv(result: dict, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    system_metrics = result.get('system_metrics', {})
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        for key, value in system_metrics.items():
            writer.writerow([key, value])
