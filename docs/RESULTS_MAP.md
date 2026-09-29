# Paper-to-artifact results map

| Paper evidence | Configuration | Frozen machine-readable evidence | Figure/table asset |
| --- | --- | --- | --- |
| RQ1 strict wait-only `O_ext` | `configs/paper/timing_oext_wait_only_loso.json` | `reference_results/results/timing_oext/wait_only_loso/` | `figures/published/figure2_timing_main.pdf` |
| RQ1 wait + status | `configs/paper/timing_oext_wait_status_loso.json` | `reference_results/results/timing_oext/wait_status_loso/summary_multiseed.json` | Paper Table for tenant-visible feature sets |
| RQ1 wait + public backend | `configs/paper/timing_oext_wait_backend_loso.json` | `reference_results/results/timing_oext/wait_backend_loso/summary_multiseed.json` | Paper Table for tenant-visible feature sets |
| RQ1 controlled pairs | Three `timing_pair_*_oext.json` files | `reference_results/results/timing_pairs/` and `timing_pairs_extra/` | Main controlled-pair tables |
| RQ1 classifier sensitivity | Frozen wait-only traces | `reference_results/results/reviewer_sensitivity/` | Text sensitivity result |
| RQ2 raw/restricted `O_sb` | `configs/paper/timing_osb.json` | `reference_results/results/timing/summary_multiseed_loso.json` | `figures/published/figure2_timing_main.pdf` |
| RQ2 monotone release controls | `configs/paper/timing_oext_release_tradeoff.json` | `reference_results/results/timing_oext/release_tradeoff/summary_tradeoff.json` | Main release-tradeoff table |
| RQ2 classical queue control | `configs/paper/timing_paired_contrast.json` | `reference_results/results/ablations/timing_paired_contrast.json` | `figures/published/timing_classical_queue_contrast.pdf` |
| RQ2 observability ladder | `configs/paper/timing_observability_ladder.json` | Frozen CSV/table inputs | `figures/published/timing_observability_ladder.pdf` |
| RQ2 repeated-seed check | `configs/paper/timing_stability.json` | `reference_results/results/stability/timing_stability.json` | `figures/published/timing_stability_by_seed.pdf` |
| RQ3 compilation controls | `configs/paper/timing_compile_awareness_oint.json` | `reference_results/results/ablations/timing_compile_awareness_loso.json` and tables | `figures/published/figure3_compilation_conditioned_observability.pdf` |
| RQ3 64-setting sweep | `configs/paper/timing_compile_sweep.json` | `reference_results/results/sweeps/timing_compile_configuration_sweep.json` and tables | Figure 3 configuration panel |
| RQ3 backend heterogeneity | `configs/paper/timing_noise_heterogeneity.json` | `reference_results/results/ablations/timing_noise_heterogeneity.json` and tables | `figures/published/figure4_backend_heterogeneity_observability.pdf` |
| RQ4 six public-backend runs | `configs/paper/timing_hardware.json` | `reference_results/results/hardware/timing_hardware_summary_ibm_kingston_6runs_2026-07-01_144002.json` | `figures/published/figure4_limited_public_backend_timing.pdf` |

The filename of the accepted hardware figure retains the historical `figure4_` prefix even though it appears later in the final manuscript. It is preserved verbatim for provenance.

Provider-issued hardware job identifiers are removed from the public reference JSON. Class labels, elapsed-time observations, backend-state context, block structure, and aggregate statistics are retained.
