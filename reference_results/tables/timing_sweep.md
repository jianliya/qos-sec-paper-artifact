<!-- semantics: Sensitivity / tradeoff evidence line; use as auxiliary support rather than as the primary paper result. -->

| dimension | value | series | leakage_advantage |
| --- | --- | --- | --- |
| probe_jobs | 120 | timing | 0.224 |
| probe_jobs | 220 | timing | 0.1193 |
| probe_jobs | 320 | timing | 0.0832 |
| benign_jobs | 20 | timing | 0.125 |
| benign_jobs | 30 | timing | 0.1193 |
| benign_jobs | 45 | timing | 0.1471 |
| workload_profile | controlled | timing | 0.1193 |
| workload_profile | shared_cloud_light | timing | 0.1436 |
| workload_profile | shared_cloud_bursty | timing | 0.1187 |
| workload_profile | shared_cloud_heavy | timing | 0.0945 |
| pressure_multiplier | 0.9 | timing | 0.1256 |
| pressure_multiplier | 1.0 | timing | 0.1193 |
| pressure_multiplier | 1.2 | timing | 0.1409 |
| pressure_multiplier | 1.4 | timing | 0.1358 |
| observability_mode | full | timing | 0.1193 |
| observability_mode | coarse | timing | 0.1176 |
| observability_mode | masked_backend_only | timing | 0.1023 |
| observability_mode | queue_length_only | timing | -0.0006 |
| observability_mode | masked | timing | 0.108 |
| observability_mode | jittered | timing | 0.0937 |
| observability_mode | hardened | timing | -0.0239 |
