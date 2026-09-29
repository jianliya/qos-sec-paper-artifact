<!-- semantics: Quantum-specific attribution ablation for timing leakage. Use this as the main supporting evidence that the timing signal is not merely a classical queue artifact. -->

| ablation | accuracy | leakage_advantage | defended_leakage_advantage | defense_gain | class_gap | classB_minus_noVictim | highIsolation_delta_from_classA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| main_quantum | 0.6582 | 0.1582 | -0.0162 | 0.1744 | 0.0385 | 0.0639 | 0.0272 |
| uniform_backend_quality | 0.673 | 0.173 | -0.0162 | 0.1892 | 0.0508 | 0.0566 | 0.0287 |
| no_calibration_drift | 0.65 | 0.15 | -0.0162 | 0.1662 | 0.0432 | 0.0702 | 0.0258 |
| topology_insensitive | 0.6574 | 0.1574 | -0.0162 | 0.1736 | 0.0428 | 0.0698 | 0.0191 |
| compile_path_neutralized | 0.6273 | 0.1273 | -0.0162 | 0.1435 | 0.0318 | 0.0499 | 0.0174 |
| noise_flattened | 0.6582 | 0.1582 | -0.0162 | 0.1744 | 0.0385 | 0.0639 | 0.0272 |
| no_coexecution_sensitivity | 0.6645 | 0.1645 | -0.0162 | 0.1807 | 0.0359 | 0.0611 | 0.0237 |
| classical_queue_baseline | 0.558 | 0.058 | -0.0162 | 0.0742 | 0.032 | 0.034 | 0.011 |
| coarse_observability_baseline | 0.6614 | 0.1614 | -0.0162 | 0.1776 | 0.0385 | 0.0639 | 0.0272 |
| masked_backend_only_baseline | 0.6224 | 0.1225 | -0.0162 | 0.1387 | 0.0385 | 0.0639 | 0.0272 |
| queue_length_only_baseline | 0.4986 | -0.0014 | -0.0162 | 0.0148 | 0.0 | 0.0 | 0.0 |
