from __future__ import annotations

from pathlib import Path

from evaluation.export_figures import export_timing

ROOT = Path(__file__).resolve().parents[2]

if __name__ == '__main__':
    export_timing(ROOT / 'results' / 'timing' / 'summary_multiseed.json', ROOT / 'plots' / 'timing')
