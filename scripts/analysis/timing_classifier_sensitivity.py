from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.stats import t


SEEDS = tuple(range(42, 58))
CLASSES = ("classA", "classB")


def _load_runs(input_dir: Path) -> tuple[list[dict], dict[str, str]]:
    runs: list[dict] = []
    hashes: dict[str, str] = {}
    for seed in SEEDS:
        path = input_dir / f"summary_seed_{seed}.json"
        payload = path.read_bytes()
        run = json.loads(payload)
        if int(run["seed"]) != seed:
            raise ValueError(f"{path} records seed {run['seed']}, expected {seed}")
        for class_name in CLASSES:
            traces = run["scenarios"][class_name]["probe_traces"]
            if len(traces) != 220:
                raise ValueError(f"{path}: {class_name} has {len(traces)} traces, expected 220")
        runs.append(run)
        hashes[path.name] = hashlib.sha256(payload).hexdigest()
    return runs, hashes


def _waits(run: dict, class_name: str) -> np.ndarray:
    return np.asarray(
        [[float(item["observed_wait"])] for item in run["scenarios"][class_name]["probe_traces"]],
        dtype=float,
    )


def _design(z: np.ndarray, model: str) -> np.ndarray:
    if model == "quadratic_logistic":
        return np.column_stack((z, z**2))
    return z


def _fit_logistic(z: np.ndarray, y: np.ndarray, model: str) -> tuple[np.ndarray, float]:
    design = _design(z, model)

    def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
        weights = params[:-1]
        bias = params[-1]
        scores = design @ weights + bias
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(scores, -40.0, 40.0)))
        loss = np.logaddexp(0.0, scores).sum() - y @ scores + 0.5 * weights @ weights
        gradient = np.concatenate((design.T @ (probabilities - y) + weights, [(probabilities - y).sum()]))
        return float(loss), gradient

    result = minimize(
        objective,
        np.zeros(design.shape[1] + 1),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8},
    )
    if not result.success:
        raise RuntimeError(f"logistic optimization failed: {result.message}")
    return result.x[:-1], float(result.x[-1])


def _fold_accuracy(runs: list[dict], heldout: int, model: str) -> float:
    train_a = np.vstack([_waits(run, "classA") for index, run in enumerate(runs) if index != heldout])
    train_b = np.vstack([_waits(run, "classB") for index, run in enumerate(runs) if index != heldout])
    test_a = _waits(runs[heldout], "classA")
    test_b = _waits(runs[heldout], "classB")

    train = np.vstack((train_a, train_b))
    mean = train.mean(axis=0)
    std = train.std(axis=0)
    std[std < 1e-9] = 1.0
    train_a = (train_a - mean) / std
    train_b = (train_b - mean) / std
    test_a = (test_a - mean) / std
    test_b = (test_b - mean) / std

    if model == "centroid":
        centroid_a = train_a.mean(axis=0)
        centroid_b = train_b.mean(axis=0)
        weights = centroid_b - centroid_a
        bias = float(-weights @ ((centroid_a + centroid_b) / 2.0))
        score_a = test_a @ weights + bias
        score_b = test_b @ weights + bias
    else:
        labels = np.concatenate((np.zeros(len(train_a)), np.ones(len(train_b))))
        weights, bias = _fit_logistic(np.vstack((train_a, train_b)), labels, model)
        score_a = _design(test_a, model) @ weights + bias
        score_b = _design(test_b, model) @ weights + bias

    correct = int((score_a < 0.0).sum() + (score_b >= 0.0).sum())
    return correct / (len(score_a) + len(score_b))


def _summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    mean = float(array.mean())
    std = float(array.std(ddof=1))
    half_width = float(t.ppf(0.975, len(array) - 1) * std / math.sqrt(len(array)))
    return {
        "mean": mean,
        "std": std,
        "ci95_half_width": half_width,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
    }


def analyze(input_dir: Path) -> dict:
    runs, hashes = _load_runs(input_dir)
    models = ("centroid", "logistic", "quadratic_logistic")
    folds = [
        {
            "seed": SEEDS[index],
            **{model: _fold_accuracy(runs, index, model) for model in models},
        }
        for index in range(len(runs))
    ]
    summaries = {model: _summary([fold[model] for fold in folds]) for model in models}
    paired = {}
    for model in models[1:]:
        deltas = [fold[model] - fold["centroid"] for fold in folds]
        paired[f"{model}_minus_centroid"] = {**_summary(deltas), "fold_deltas": deltas}
    return {
        "analysis": "wait-only classifier sensitivity under leave-one-seed-out evaluation",
        "independent_groups": 16,
        "traces_per_class_per_group": 220,
        "feature": "observed_wait",
        "normalization": "training-fold mean and population standard deviation only",
        "models": {
            "centroid": "nearest linear centroid separator",
            "logistic": "logistic regression with fixed L2 penalty 0.5*||w||^2",
            "quadratic_logistic": "same fixed logistic objective over [z, z^2]",
        },
        "model_selection": "none; all specifications fixed before inspecting fold results",
        "input_directory": str(input_dir.resolve()),
        "input_sha256": hashes,
        "folds": folds,
        "summaries": summaries,
        "paired_differences": paired,
        "provenance_warning": (
            "These archived raw traces must be matched to the manuscript's frozen primary endpoint "
            "before their numerical results are inserted into the paper."
        ),
    }


def _write_outputs(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "timing_classifier_sensitivity.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    with (output_dir / "timing_classifier_sensitivity_folds.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("seed", "centroid", "logistic", "quadratic_logistic"))
        writer.writeheader()
        writer.writerows(result["folds"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.input_dir)
    _write_outputs(result, args.output_dir)
    for model, summary in result["summaries"].items():
        print(f"{model}: {summary['mean']:.4f} +/- {summary['ci95_half_width']:.4f}")


if __name__ == "__main__":
    main()
