<!-- semantics: Lightweight compile-aware timing experiment. Interpret it as engineering-chain support that transpilation outputs can reshape scheduler-visible timing and backend-choice observability, not as the primary paper result. -->

| family | backend_id | backend_qubits | compiled_depth | cx_count | swap_count | layout_span | expected_fidelity | backend_suitability | topology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| small_qaoa | fallback_fake_0 | 7 | 24 | 21 | 4 | 7 | 0.8268 | 0.7513 | line |
| small_qaoa | fallback_fake_1 | 13 | 17 | 14 | 2 | 5 | 0.81 | 0.7604 | ladder |
| small_qaoa | fallback_fake_2 | 27 | 14 | 11 | 1 | 5 | 0.7747 | 0.7088 | grid |
| bv_like | fallback_fake_0 | 7 | 10 | 5 | 1 | 6 | 0.9078 | 0.8587 | line |
| bv_like | fallback_fake_1 | 13 | 10 | 2 | 0 | 5 | 0.8649 | 0.8453 | ladder |
| bv_like | fallback_fake_2 | 27 | 10 | 2 | 0 | 5 | 0.8131 | 0.7622 | grid |
| grover_like | fallback_fake_0 | 7 | 25 | 21 | 4 | 7 | 0.8308 | 0.7367 | line |
| grover_like | fallback_fake_1 | 13 | 16 | 11 | 1 | 6 | 0.8254 | 0.7908 | ladder |
| grover_like | fallback_fake_2 | 27 | 16 | 11 | 1 | 6 | 0.7736 | 0.7077 | grid |
| random | fallback_fake_0 | 7 | 38 | 34 | 7 | 7 | 0.7722 | 0.6146 | line |
| random | fallback_fake_1 | 13 | 26 | 21 | 3 | 8 | 0.7744 | 0.7091 | ladder |
| random | fallback_fake_2 | 27 | 20 | 15 | 1 | 7 | 0.7602 | 0.6943 | grid |
| mirror | fallback_fake_0 | 7 | 30 | 26 | 5 | 7 | 0.812 | 0.6844 | line |
| mirror | fallback_fake_1 | 13 | 21 | 16 | 2 | 7 | 0.8022 | 0.7519 | ladder |
| mirror | fallback_fake_2 | 27 | 18 | 13 | 1 | 7 | 0.7669 | 0.701 | grid |
