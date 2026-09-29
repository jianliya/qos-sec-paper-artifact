from __future__ import annotations

from pathlib import Path

from evaluation.export_figures import export_availability

ROOT = Path(__file__).resolve().parents[2]

if __name__ == '__main__':
    export_availability(ROOT / 'results' / 'availability' / 'summary_multiseed.json', ROOT / 'plots' / 'availability')
