<!-- semantics: Paired timing attribution contrasts on identical per-seed workloads/backends with only one factor flipped. Use this as the strongest attribution-strengthening evidence line. -->

| contrast | reference | compare | delta_leakage_advantage | delta_leakage_ci95 | delta_threshold_leakage_advantage | delta_threshold_leakage_ci95 | delta_defense_gain | delta_defense_gain_ci95 | delta_class_gap | delta_class_gap_ci95 | positive_delta_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| main_vs_classical_queue | main_quantum | classical_queue_baseline | 0.1003 | 0.0368 | 0.0142 | 0.0381 | 0.1003 | 0.0368 | 0.0065 | 0.0069 | 0.9375 |
| main_vs_uniform_backend_quality | main_quantum | uniform_backend_quality | -0.0148 | 0.0263 | -0.0009 | 0.0408 | -0.0148 | 0.0263 | -0.0123 | 0.0074 | 0.375 |
| main_vs_no_coexecution_sensitivity | main_quantum | no_coexecution_sensitivity | -0.0063 | 0.0111 | 0.0025 | 0.0082 | -0.0063 | 0.0111 | 0.0025 | 0.0017 | 0.375 |
| main_vs_no_calibration_drift | main_quantum | no_calibration_drift | 0.0082 | 0.0277 | 0.0014 | 0.0451 | 0.0082 | 0.0277 | -0.0047 | 0.0095 | 0.5 |
| main_vs_topology_insensitive | main_quantum | topology_insensitive | 0.0009 | 0.0317 | 0.0486 | 0.0301 | 0.0009 | 0.0317 | -0.0043 | 0.0056 | 0.5 |
| main_vs_compile_path_neutralized | main_quantum | compile_path_neutralized | 0.031 | 0.0207 | 0.0534 | 0.0305 | 0.031 | 0.0207 | 0.0067 | 0.0046 | 0.6875 |
| main_vs_noise_flattened | main_quantum | noise_flattened | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| main_vs_coarse_observability | main_quantum | coarse_observability_baseline | -0.0031 | 0.0063 | -0.0003 | 0.0021 | -0.0031 | 0.0063 | -0.0 | 0.0 | 0.25 |
| main_vs_masked_backend_only | main_quantum | masked_backend_only_baseline | 0.0358 | 0.0217 | 0.0 | 0.0 | 0.0358 | 0.0217 | 0.0 | 0.0 | 0.8125 |
| main_vs_queue_length_only | main_quantum | queue_length_only_baseline | 0.1596 | 0.0201 | 0.1145 | 0.0378 | 0.1596 | 0.0201 | 0.0385 | 0.0064 | 1.0 |
