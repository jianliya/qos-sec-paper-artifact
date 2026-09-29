from __future__ import annotations

from pathlib import Path

from evaluation.compare_baselines import run_baseline_comparison
from evaluation.export_results import export_json, export_system_csv
from scenarios.backend_scarcity import build_scenario as scarcity
from scenarios.contention_heavy import build_scenario as heavy
from scenarios.contention_light import build_scenario as light
from scenarios.mixed_sensitivity import build_scenario as mixed
from scenarios.profile_driven import PROFILE_SCENARIOS


LEGACY_SCENARIOS = {
    'contention_light': light,
    'contention_heavy': heavy,
    'mixed_sensitivity': mixed,
    'backend_scarcity': scarcity,
}

SCENARIOS = PROFILE_SCENARIOS


def run_main_experiment(output_dir: str | Path):
    output_dir = Path(output_dir)
    results = {}
    for name, builder in SCENARIOS.items():
        scenario_result = run_baseline_comparison(builder())
        results[name] = scenario_result
        export_json(scenario_result, output_dir / f'{name}.json')
        for scheduler_name, summary in scenario_result.items():
            export_system_csv(
                {'system_metrics': summary['system_metrics']},
                output_dir / f'{name}_{scheduler_name}_system.csv',
            )
    return results


def run_legacy_main_experiment(output_dir: str | Path):
    output_dir = Path(output_dir)
    results = {}
    for name, builder in LEGACY_SCENARIOS.items():
        scenario_result = run_baseline_comparison(builder())
        results[name] = scenario_result
        export_json(scenario_result, output_dir / f'{name}.json')
        for scheduler_name, summary in scenario_result.items():
            export_system_csv(
                {'system_metrics': summary['system_metrics']},
                output_dir / f'{name}_{scheduler_name}_system.csv',
            )
    return results
