from __future__ import annotations

from evaluation.compare_baselines import run_baseline_comparison
from evaluation.export_results import export_json
from evaluation.metric_tables import export_primary_metric_table
from evaluation.tradeoff import summarize_tradeoff
from scenarios.parameterized import build_parameterized_contention_scenario


PRESSURE_LEVELS = ['light', 'medium', 'heavy']
VICTIM_RATIOS = [0.2, 0.4]
SCARCE_BACKEND_RATIOS = [0.5, 1.0]
MODES = ['single', 'session']


def run_parameter_sweep(output_dir):
    from pathlib import Path
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results = {}

    for pressure in PRESSURE_LEVELS:
        for victim_ratio in VICTIM_RATIOS:
            for scarcity in SCARCE_BACKEND_RATIOS:
                for mode in MODES:
                    key = f'p={pressure}_v={victim_ratio}_s={scarcity}_m={mode}'

                    def builder(p=pressure, v=victim_ratio, s=scarcity, m=mode):
                        return build_parameterized_contention_scenario(
                            pressure_level=p,
                            victim_ratio=v,
                            scarce_backend_ratio=s,
                            mode=m,
                        )

                    results = run_baseline_comparison(builder())
                    all_results[key] = {
                        'comparison': results,
                        'tradeoff': summarize_tradeoff(results),
                    }
                    export_json(all_results[key], output_dir / f'{key}.json')
                    export_primary_metric_table(results, output_dir / f'{key}_primary_metrics.csv')
    return all_results
