from __future__ import annotations

from evaluation.statistics import summarize


def aggregate_named_runs(
    runs: list[dict],
    names: list[str],
    metrics: list[str],
    *,
    ci_method: str = "normal",
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 0,
) -> dict:
    out = {"num_seeds": len(runs), "seeds": [r["seed"] for r in runs], "scenarios": {}}
    for name in names:
        out["scenarios"][name] = {}
        for metric in metrics:
            vals = [r[name][metric] for r in runs]
            out["scenarios"][name][metric] = summarize(
                vals,
                ci_method=ci_method,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=bootstrap_seed,
            )
    return out


def aggregate_metrics(
    runs: list[dict],
    metrics: list[str],
    *,
    ci_method: str = "normal",
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 0,
) -> dict:
    return {
        "num_seeds": len(runs),
        "seeds": [r["seed"] for r in runs],
        "metrics": {
            metric: summarize(
                [r[metric] for r in runs],
                ci_method=ci_method,
                bootstrap_iterations=bootstrap_iterations,
                bootstrap_seed=bootstrap_seed,
            )
            for metric in metrics
        },
    }
