# qos-sec paper artifact

This repository is the reproducibility artifact for:

> Liya Jian and Yuqing Lan, "Scheduler-Boundary Observability in Shared Quantum Clouds: Compilation- and Backend-Conditioned Diagnostics," *Computation*, vol. 14, no. 9, article 197, 2026. [https://doi.org/10.3390/computation14090197](https://doi.org/10.3390/computation14090197)

The artifact contains the runnable prototype, the configurations used for the final paper, frozen machine-readable results, the accepted figures, and checks that connect the archived results to the numerical claims in the article.

## What the artifact evaluates

The paper separates three observation spaces:

| View | Access | Evidentiary role |
| --- | --- | --- |
| `O_ext` | Tenant-visible | Evidence over released service fields, primarily provider-reported waiting time |
| `O_sb` | Provider audit | Pre-release scheduler-boundary mechanism support |
| `O_int` | Provider/researcher | Compilation- and backend-conditioned internal diagnostics |

The public-backend experiment is a separate, limited in-sample feasibility check. It is not an out-of-sample attack evaluation and does not approximate IBM's proprietary scheduler.

## Repository layout

```text
configs/paper/          Frozen configurations for RQ1--RQ4
src/                    Full prototype and evaluation implementation
scripts/                Unified reproduction, validation, and plotting tools
reference_results/      Immutable results and tables used by the accepted paper
results/                Fresh outputs created by reproduction runs (Git-ignored)
figures/published/      PDFs in the accepted manuscript
figures/generated/      Regenerated figures (Git-ignored)
docs/                   Evidence map, protocol, and release notes
tests/                  Lightweight artifact tests
```

Fresh runs never overwrite `reference_results/`.

## Installation

Python 3.12 is the environment used for the archived run. Python 3.10--3.12 is accepted by the package metadata.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Windows PowerShell activation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

For the optional IBM Runtime path:

```bash
python -m pip install -e ".[hardware]"
```

`requirements-lock.txt` records the complete working environment used during manuscript revision. The smaller `requirements.txt` contains only the direct analysis dependencies.

## Fast validation

First validate the frozen evidence without rerunning experiments:

```bash
python scripts/verify_reference_results.py
python -m unittest discover -s tests -v
```

Then run the deterministic seed-42 smoke experiment:

```bash
python scripts/reproduce.py quick
```

The smoke run checks the following seed-42 values at the paper's four-decimal reporting precision:

| Metric | Expected |
| --- | ---: |
| Class A mean wait | 0.4529 |
| Class B mean wait | 0.5064 |
| Raw accuracy | 0.6318 |
| Defended accuracy | 0.5045 |
| Raw-to-defended reduction | 0.1273 |

## Reproduce the evidence families

List the available experiment groups:

```bash
python scripts/reproduce.py --list
```

Run the main evidence families:

```bash
python scripts/reproduce.py rq1-main
python scripts/reproduce.py rq2-boundary
python scripts/reproduce.py rq3-diagnostics
```

Run expensive auxiliary analyses only when needed:

```bash
python scripts/reproduce.py rq1-aux
python scripts/reproduce.py appendix
```

The grouped significance analysis is intentionally part of `rq1-aux`; it is substantially slower than the quick and main runs.

The public-backend experiment is not run by any aggregate command. It consumes external service quota and requires explicit invocation:

```bash
export IBM_QUANTUM_TOKEN="..."
python scripts/reproduce.py rq4-hardware
```

PowerShell:

```powershell
$env:IBM_QUANTUM_TOKEN = "..."
python scripts/reproduce.py rq4-hardware
```

Never place the token in a JSON configuration or commit it to Git.

## Regenerate figures

The accepted PDFs are preserved in `figures/published/`. To regenerate the data-driven figures from the frozen reference results:

```bash
python scripts/generate_paper_figures.py
```

Generated files are written to `figures/generated/` so that they can be compared with, but cannot overwrite, the accepted figures.

## Reproduce the classifier sensitivity check

```bash
python scripts/analysis/timing_classifier_sensitivity.py \
  --input-dir reference_results/results/timing_oext/wait_only_loso \
  --output-dir results/classifier_sensitivity
```

The analysis fixes the centroid, L2-logistic, and predetermined quadratic-logistic specifications before evaluating the same 16 seed-held-out folds.

## Important interpretation boundaries

- The principal `O_ext` field is provider-reported waiting time, not independently measured tenant wall-clock latency.
- The 220 probes within one workload seed are correlated repeated observations. The independent workload-realization count is 16 seeds.
- `O_sb` and `O_int` are provider-side audit views; they are not tenant attack inputs.
- Synthetic IBM-style backend abstractions do not model IBM's proprietary scheduling implementation.
- Static backend-quality regimes are controlled diagnostic profiles, not reconstructed time-varying calibration histories.
- The six-run public-backend check is weak, variable, in-sample evidence on one backend.
- The results do not establish that the external signal has a uniquely quantum cause or that a practical public-cloud attack exists.

See [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for the complete command map and [docs/RESULTS_MAP.md](docs/RESULTS_MAP.md) for the paper-to-artifact correspondence.

## Citation and license

Citation metadata are provided in `CITATION.cff`. Please cite the associated article using DOI [10.3390/computation14090197](https://doi.org/10.3390/computation14090197).

The software and accompanying repository materials are released under the MIT License. See `LICENSE`.
