from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from evaluation.export_figures import (
        export_ablation,
        export_appendix_bundle,
        export_availability,
        export_timing,
        export_timing_ablation,
        export_timing_quantum_ablation,
        export_timing_stability,
        export_tradeoff_from_availability,
        export_tradeoff_from_sweeps,
    )
    FIGURE_EXPORTS_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    export_ablation = None
    export_appendix_bundle = None
    export_availability = None
    export_timing = None
    export_timing_ablation = None
    export_timing_quantum_ablation = None
    export_timing_stability = None
    export_tradeoff_from_availability = None
    export_tradeoff_from_sweeps = None
    FIGURE_EXPORTS_AVAILABLE = False
from evaluation.export_tables import (
    export_ablation_tables,
    export_availability_tables,
    export_hardware_timing_tables,
    export_sweep_tables,
    export_timing_ablation_tables,
    export_timing_compile_awareness_tables,
    export_timing_compile_configuration_sweep_tables,
    export_timing_noise_heterogeneity_tables,
    export_timing_paired_contrast_tables,
    export_timing_quantum_ablation_tables,
    export_timing_stability_tables,
    export_timing_tables,
)
from scenarios import availability, timing_hardware, timing_leakage

ROOT = Path(__file__).resolve().parents[2]

SCENARIO_HELP = {
    'availability': 'Scheduler comparison under adversarial pressure. Interpret the main output as delay-based service degradation evidence rather than a clean baseline/attack/defense benchmark.',
    'timing': 'Prototype-side timing distinguishability study. The main defended output is a joint configuration: secure_joint scheduling plus hardened observability shaping.',
    'timing-hardware': 'Limited hardware feasibility check for timing observability on a public IBM backend under a tight runtime budget.',
    'availability-sweep': 'Auxiliary availability sensitivity / tradeoff sweep over stressed-workload parameters; not the primary paper result.',
    'timing-sweep': 'Auxiliary timing sensitivity / tradeoff sweep over probe volume or observability settings; not the primary paper result.',
    'availability-ablation': 'Auxiliary availability-side scheduler ablation used to unpack protection-performance tradeoffs.',
    'timing-ablation': 'Auxiliary timing-side ablation over defended variants / observability-shaping components.',
    'timing-quantum-ablation': 'Quantum-specific attribution ablation for timing leakage. This evidence line tests whether backend heterogeneity, calibration drift, topology-sensitive placement, co-execution sensitivity, and non-classical scheduling conditions materially shape scheduler-visible distinguishability.',
    'timing-paired-contrast': 'Paired timing attribution contrasts on identical per-seed workloads/backends with only one factor flipped. This is the strongest follow-up evidence line for quantum attribution strengthening.',
    'timing-compile-awareness': 'Lightweight compile-aware experiment that injects Qiskit transpilation outputs into scheduler-visible features and measures how timing and backend-choice observability shift.',
    'timing-compile-sweep': 'Second-layer compile sweep over optimization level, transpiler seed, and a minimal layout/routing 2x2 subset. This is the smallest configuration-sensitivity entry before any larger compilation matrix.',
    'timing-noise-heterogeneity': 'Lightweight noise-heterogeneity ablation that probes whether backend quality variation amplifies timing observability, destabilizes it, or mainly shifts victim-side quality.',
    'timing-stability': 'Auxiliary robustness summary for the defended timing configuration across multiple seeds.',
    'timing-probe-budget': 'Strict O_ext wait-only probe-budget curve under secret-bundle LOSO evaluation. Use it to relate attack signal to how many probe jobs are consumed per inference on one secret.',
    'timing-significance': 'Seed-structured significance analysis for strict O_ext timing. Runs seed-level label permutation nulls and cluster bootstrap intervals for trace-level and bundle-level leakage metrics.',
    'timing-scheduler-comparison': 'Strict O_ext wait-only comparison across multiple scheduler logics. Use it to bound how policy-specific the main signal is.',
    'timing-controlled-pair-compile-stats': 'Compile-statistics summary for controlled workload pairs. Use it to report post-compilation differences rather than leaving them implicit.',
    'export-tables': 'Export semantically annotated result tables. Main / ablation / stability / sweep outputs are different evidence lines and should not be mixed casually.',
    'export-appendix': 'Export appendix-ready plots and bundles from the current main / ablation / stability / sweep result files.',
}


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _require_figure_exports() -> None:
    if not FIGURE_EXPORTS_AVAILABLE:
        raise ModuleNotFoundError(
            'Figure export dependencies are unavailable. Install matplotlib to enable plot export, or run scenarios without export steps.'
        )


def _timing_sweep_output_path(cfg: dict) -> Path:
    return ROOT / 'results' / 'sweeps' / cfg.get('output_filename', 'timing_sweep.json')


def _export_all_tables() -> None:
    export_availability_tables(ROOT / 'results' / 'availability' / 'summary_multiseed.json', ROOT / 'tables')
    export_timing_tables(ROOT / 'results' / 'timing' / 'summary_multiseed.json', ROOT / 'tables')
    export_ablation_tables(ROOT / 'results' / 'ablations' / 'availability_ablation.json', ROOT / 'tables')
    if (ROOT / 'results' / 'ablations' / 'timing_ablation.json').exists():
        export_timing_ablation_tables(ROOT / 'results' / 'ablations' / 'timing_ablation.json', ROOT / 'tables')
    if (ROOT / 'results' / 'ablations' / 'timing_quantum_ablation.json').exists():
        export_timing_quantum_ablation_tables(ROOT / 'results' / 'ablations' / 'timing_quantum_ablation.json', ROOT / 'tables')
    if (ROOT / 'results' / 'ablations' / 'timing_paired_contrast.json').exists():
        export_timing_paired_contrast_tables(ROOT / 'results' / 'ablations' / 'timing_paired_contrast.json', ROOT / 'tables')
    if (ROOT / 'results' / 'ablations' / 'timing_compile_awareness.json').exists():
        export_timing_compile_awareness_tables(ROOT / 'results' / 'ablations' / 'timing_compile_awareness.json', ROOT / 'tables')
    if (ROOT / 'results' / 'sweeps' / 'timing_compile_configuration_sweep.json').exists():
        export_timing_compile_configuration_sweep_tables(ROOT / 'results' / 'sweeps' / 'timing_compile_configuration_sweep.json', ROOT / 'tables')
    if (ROOT / 'results' / 'ablations' / 'timing_noise_heterogeneity.json').exists():
        export_timing_noise_heterogeneity_tables(ROOT / 'results' / 'ablations' / 'timing_noise_heterogeneity.json', ROOT / 'tables')
    if (ROOT / 'results' / 'stability' / 'timing_stability.json').exists():
        export_timing_stability_tables(ROOT / 'results' / 'stability' / 'timing_stability.json', ROOT / 'tables')
    if (ROOT / 'results' / 'hardware' / 'timing_hardware_summary.json').exists():
        export_hardware_timing_tables(ROOT / 'results' / 'hardware' / 'timing_hardware_summary.json', ROOT / 'tables')
    export_sweep_tables(ROOT / 'results' / 'sweeps' / 'availability_sweep.json', ROOT / 'tables', 'secure_joint', 'victim_avg_wait', 'availability_sweep')
    export_sweep_tables(ROOT / 'results' / 'sweeps' / 'timing_sweep.json', ROOT / 'tables', 'timing', 'leakage_advantage', 'timing_sweep')


def _export_appendix() -> None:
    _require_figure_exports()
    appendix_dir = ROOT / 'plots' / 'appendix'
    appendix_dir.mkdir(parents=True, exist_ok=True)
    export_tradeoff_from_availability(ROOT / 'results' / 'availability' / 'summary_multiseed.json', ROOT / 'plots' / 'tradeoff')
    export_tradeoff_from_sweeps(ROOT / 'results' / 'sweeps' / 'availability_sweep.json', ROOT / 'plots' / 'tradeoff')
    export_tradeoff_from_sweeps(ROOT / 'results' / 'sweeps' / 'timing_sweep.json', ROOT / 'plots' / 'tradeoff')
    if (ROOT / 'results' / 'ablations' / 'timing_ablation.json').exists():
        export_timing_ablation(ROOT / 'results' / 'ablations' / 'timing_ablation.json', ROOT / 'plots' / 'ablations')
    if (ROOT / 'results' / 'ablations' / 'timing_quantum_ablation.json').exists():
        export_timing_quantum_ablation(ROOT / 'results' / 'ablations' / 'timing_quantum_ablation.json', ROOT / 'plots' / 'ablations')
    if (ROOT / 'results' / 'stability' / 'timing_stability.json').exists():
        export_timing_stability(ROOT / 'results' / 'stability' / 'timing_stability.json', ROOT / 'plots' / 'timing')
    export_appendix_bundle(appendix_dir, {
        'availability_main': ROOT / 'plots' / 'availability' / 'victim_wait.svg',
        'timing_main': ROOT / 'plots' / 'timing' / 'signal_metrics.svg',
        'availability_tradeoff': ROOT / 'plots' / 'tradeoff' / 'availability_tradeoff.svg',
        'availability_ablation': ROOT / 'plots' / 'ablations' / 'ablation_wait.svg',
        'timing_ablation': ROOT / 'plots' / 'ablations' / 'timing_ablation_gain.svg',
        'timing_stability': ROOT / 'plots' / 'timing' / 'timing_stability_summary.svg',
    })


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'Run qos-sec paper-oriented experiments. '\
            'This CLI drives a threat-model-driven prototype / simulation framework; '\
            'the availability, timing, ablation, stability, sweep, and hardware commands correspond to different evidence lines.'
        )
    )
    parser.add_argument(
        'scenario',
        choices=list(SCENARIO_HELP.keys()),
        help='Scenario family to run. See docs/results_semantics.md for the canonical meaning of each evidence line.',
    )
    parser.add_argument(
        '--config',
        default=None,
        help='Optional path to a config JSON. If omitted, the default config for the selected scenario is used.',
    )
    parser.add_argument(
        '--single-seed',
        action='store_true',
        help='Run only the configured single seed for availability or timing main scenarios instead of the full multi-seed aggregate.',
    )
    args = parser.parse_args()

    scenario_to_config = {
        'availability': 'availability.json',
        'timing': 'timing_oext_wait_only_loso.json',
        'timing-hardware': 'timing_hardware.json',
        'availability-sweep': 'availability_sweep.json',
        'timing-sweep': 'timing_sweep.json',
        'availability-ablation': 'availability_ablation.json',
        'timing-ablation': 'timing_ablation.json',
        'timing-quantum-ablation': 'timing_quantum_ablation.json',
        'timing-paired-contrast': 'timing_paired_contrast.json',
        'timing-compile-awareness': 'timing_compile_awareness_oint.json',
        'timing-compile-sweep': 'timing_compile_sweep.json',
        'timing-noise-heterogeneity': 'timing_noise_heterogeneity.json',
        'timing-stability': 'timing_stability.json',
        'timing-probe-budget': 'timing_probe_budget.json',
        'timing-significance': 'timing_significance.json',
        'timing-scheduler-comparison': 'timing_scheduler_comparison.json',
        'timing-controlled-pair-compile-stats': 'timing_controlled_pair_compile_stats.json',
        'export-tables': 'appendix.json',
        'export-appendix': 'appendix.json',
    }
    if args.config:
        config_path = Path(args.config)
    else:
        candidate = ROOT / 'configs' / scenario_to_config[args.scenario]
        paper_candidate = ROOT / 'configs' / 'paper' / scenario_to_config[args.scenario]
        if candidate.exists():
            config_path = candidate
        elif paper_candidate.exists():
            config_path = paper_candidate
        else:
            config_path = ROOT / 'configs' / 'legacy' / scenario_to_config[args.scenario]
    cfg = load_config(str(config_path))

    print(f'[qos-sec] scenario={args.scenario}')
    print(f'[qos-sec] semantics={SCENARIO_HELP[args.scenario]}')

    if args.scenario == 'availability':
        if args.single_seed:
            result = availability.run_once(cfg['seed'], cfg)
            out = ROOT / 'results' / 'availability' / 'summary.json'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding='utf-8')
        else:
            availability.run_multiseed(cfg)
            if FIGURE_EXPORTS_AVAILABLE:
                export_availability(ROOT / 'results' / 'availability' / 'summary_multiseed.json', ROOT / 'plots' / 'availability')
                export_tradeoff_from_availability(ROOT / 'results' / 'availability' / 'summary_multiseed.json', ROOT / 'plots' / 'tradeoff')
    elif args.scenario == 'timing':
        if args.single_seed:
            result = timing_leakage.run_once(cfg['seed'], cfg)
            out = ROOT / 'results' / 'timing' / 'summary.json'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=2), encoding='utf-8')
        else:
            timing_leakage.run_multiseed(cfg)
            if FIGURE_EXPORTS_AVAILABLE:
                export_timing(ROOT / 'results' / 'timing' / 'summary_multiseed.json', ROOT / 'plots' / 'timing')
    elif args.scenario == 'timing-hardware':
        result = timing_hardware.run_once(cfg)
        out = ROOT / 'results' / 'hardware' / 'timing_hardware_summary.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    elif args.scenario == 'availability-sweep':
        availability.run_sweep(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_tradeoff_from_sweeps(ROOT / 'results' / 'sweeps' / 'availability_sweep.json', ROOT / 'plots' / 'tradeoff')
    elif args.scenario == 'timing-sweep':
        timing_leakage.run_sweep(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_tradeoff_from_sweeps(_timing_sweep_output_path(cfg), ROOT / 'plots' / 'tradeoff')
    elif args.scenario == 'availability-ablation':
        availability.run_ablation(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_ablation(ROOT / 'results' / 'ablations' / 'availability_ablation.json', ROOT / 'plots' / 'ablations')
    elif args.scenario == 'timing-ablation':
        timing_leakage.run_ablation(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_timing_ablation(ROOT / 'results' / 'ablations' / 'timing_ablation.json', ROOT / 'plots' / 'ablations')
    elif args.scenario == 'timing-quantum-ablation':
        timing_leakage.run_quantum_ablation(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_timing_quantum_ablation(ROOT / 'results' / 'ablations' / 'timing_quantum_ablation.json', ROOT / 'plots' / 'ablations')
    elif args.scenario == 'timing-paired-contrast':
        timing_leakage.run_paired_contrast(cfg)
    elif args.scenario == 'timing-compile-awareness':
        timing_leakage.run_compile_awareness(cfg)
    elif args.scenario == 'timing-compile-sweep':
        timing_leakage.run_compile_configuration_sweep(cfg)
    elif args.scenario == 'timing-noise-heterogeneity':
        timing_leakage.run_noise_heterogeneity(cfg)
    elif args.scenario == 'timing-stability':
        timing_leakage.run_stability(cfg)
        if FIGURE_EXPORTS_AVAILABLE:
            export_timing_stability(ROOT / 'results' / 'stability' / 'timing_stability.json', ROOT / 'plots' / 'timing')
    elif args.scenario == 'timing-probe-budget':
        timing_leakage.run_probe_budget(cfg)
    elif args.scenario == 'timing-significance':
        timing_leakage.run_significance_analysis(cfg)
    elif args.scenario == 'timing-scheduler-comparison':
        timing_leakage.run_scheduler_oext_comparison(cfg)
    elif args.scenario == 'timing-controlled-pair-compile-stats':
        timing_leakage.run_controlled_pair_compile_stats(cfg)
    elif args.scenario == 'export-tables':
        _export_all_tables()
    elif args.scenario == 'export-appendix':
        _export_appendix()


if __name__ == '__main__':
    main()
