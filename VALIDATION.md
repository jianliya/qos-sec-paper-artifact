# Validation record

Validation date: 2026-09-28

## Completed checks

1. `python scripts/verify_reference_results.py`
   - 23 paper-facing JSON/CSV metric checks passed.
   - Reference-tree digest after hardware identifier sanitization:
     `9624211b7aa5c49f303eaf6357f705667f5c57122d90aa95ce481f53d90641b9`.
2. `python -m unittest discover -s tests -v`
   - 3 artifact structure and import tests passed.
3. `python scripts/reproduce.py quick`
   - Seed 42 reproduced Class A wait 0.4529, Class B wait 0.5064,
     raw accuracy 0.6318, defended accuracy 0.5045, and reduction 0.1273.
4. Classifier sensitivity analysis
   - 3 unit tests passed.
   - Centroid: 0.6010 +/- 0.0127.
   - Fixed-L2 logistic: 0.6001 +/- 0.0129.
   - Predetermined quadratic logistic: 0.6007 +/- 0.0154.
5. `python scripts/generate_paper_figures.py`
   - Generated 14 PDF figures and 4 TeX table fragments from the frozen inputs.
   - Matplotlib emitted two non-fatal `tight_layout` compatibility warnings.
6. `python scripts/secret_scan.py`
   - No obvious plaintext credentials were found in release-facing source and configuration files.
7. Hardware reference sanitization
   - 224 repeated `job_id` fields were removed from the public hardware JSON.
   - Measurements, labels, block structure, backend context, and aggregates were retained.

## Not rerun

- The complete RQ1--RQ3 experiment suite was not rerun end-to-end during packaging because several groups are computationally expensive. Frozen results were checked and the deterministic smoke endpoint was rerun.
- The IBM public-backend experiment was not rerun. A new run would consume external quota and could not recreate historical queue conditions.
- Git-history secret scanning remains necessary after the final repository history is chosen.
