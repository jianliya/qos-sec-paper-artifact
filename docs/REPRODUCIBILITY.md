# Reproducibility protocol

## 1. Reproduction levels

The artifact distinguishes three levels:

1. **Reference validation** checks the integrity and values of the frozen paper outputs without rerunning the simulator.
2. **Smoke reproduction** reruns one deterministic workload seed and compares it with the archived seed-42 endpoint.
3. **Full reproduction** reruns an evidence family using the final configuration files.

This separation prevents a quick installation test from being confused with a full 16-seed reproduction.

## 2. Reference validation

```bash
python scripts/verify_reference_results.py
python -m unittest discover -s tests -v
```

The validator checks JSON and CSV values that appear in the paper, including the main external and scheduler-boundary accuracies, the release-delay tradeoff, the classical-queue paired control, compilation-conditioned diagnostics, backend heterogeneity, and the six-run hardware summary.

## 3. Experiment map

| Command | Included experiments | Main outputs |
| --- | --- | --- |
| `quick` | Seed 42, strict wait-only `O_ext` | `results/quick/summary_seed_42.json` |
| `rq1-main` | Three external feature sets and three controlled workload pairs | `results/timing_oext/`, `results/timing_pairs/` |
| `rq1-aux` | Probe budget, scheduler comparison, grouped significance | `results/timing_oext/` |
| `rq2-boundary` | `O_sb`, monotone release controls, observability ladder, paired queue control | `results/timing/`, `results/timing_oext/`, `results/ablations/`, `results/sweeps/` |
| `rq3-diagnostics` | Compilation control, 64-setting sweep, heterogeneity, compile statistics | `results/ablations/`, `results/sweeps/`, `results/timing_pairs_compile_stats/` |
| `appendix` | Timing ablation, 20-seed stability, broader quantum-condition ablation | `results/ablations/`, `results/stability/` |
| `rq4-hardware` | Optional public-backend feasibility run | `results/hardware/` |

Each command prints the exact configuration before running it.

## 4. Individual configurations

The following files are the final paper-facing configurations:

- RQ1 external views:
  - `timing_oext_wait_only_loso.json`
  - `timing_oext_wait_status_loso.json`
  - `timing_oext_wait_backend_loso.json`
- RQ1 controlled pairs:
  - `timing_pair_width_matched_depth_diff_oext.json`
  - `timing_pair_depth_matched_structure_diff_oext.json`
  - `timing_pair_compile_divergent_oext.json`
- RQ2:
  - `timing_osb.json`
  - `timing_oext_release_tradeoff.json`
  - `timing_observability_ladder.json`
  - `timing_paired_contrast.json`
- RQ3:
  - `timing_compile_awareness_oint.json`
  - `timing_compile_sweep.json`
  - `timing_noise_heterogeneity.json`
  - `timing_controlled_pair_compile_stats.json`
- RQ4:
  - `timing_hardware.json`

## 5. Expected primary values

The frozen reference files reproduce these reported values:

| Evidence | Value |
| --- | ---: |
| `O_ext` wait-only accuracy | 0.6010 +/- 0.0127 |
| `O_ext` wait-only signed advantage | 0.1010 +/- 0.0127 |
| Shaped `O_ext` accuracy | 0.5018 +/- 0.0060 |
| Raw `O_sb` accuracy | 0.6206 +/- 0.0250 |
| Restricted `O_sb` accuracy | 0.5018 +/- 0.0060 |
| Monotone-padding residual advantage | 0.0324 +/- 0.0074 |
| Delayed-release residual advantage | 0.0418 +/- 0.0102 |
| Classical-queue paired delta | 0.1003 +/- 0.0368 |
| Hardware raw mean accuracy | 0.5312 |
| Hardware grouped diagnostic accuracy | 0.5833 |

These values have different evidentiary roles and must not be treated as interchangeable measurements.

## 6. Hardware safeguards

The hardware command:

- requires `IBM_QUANTUM_TOKEN` in the environment;
- uses the backend and run budget stated in `configs/paper/timing_hardware.json`;
- may fail if the named public backend is retired or unavailable;
- cannot be expected to reproduce historical queue conditions;
- creates a new feasibility observation rather than recreating the archived 2026 service state.

## 7. Output provenance

`reference_results/` is the immutable record used by the accepted manuscript. It should be versioned and checksummed. `results/` is reserved for fresh runs and is ignored by Git. Do not copy new results into the reference tree without creating a new tagged artifact release and documenting the change.
