# Public release checklist

- [x] Confirm code ownership and select the MIT License.
- [x] Replace `LICENSE-STATUS.md` with the approved `LICENSE` file.
- [x] Add the final article DOI to `README.md` and `CITATION.cff`.
- [x] Run `python scripts/verify_reference_results.py`.
- [x] Run `python -m unittest discover -s tests -v`.
- [x] Run `python scripts/reproduce.py quick` in a clean environment.
- [x] Run `python scripts/secret_scan.py` and review every reported match.
- [x] Confirm that no IBM token, account identifier, private project identifier, or unnecessary job identifier is present.
- [x] If the hardware reference is replaced, rerun `python scripts/sanitize_hardware_reference.py`.
- [x] Review `git diff --cached` before committing; do not use `git add .` blindly.
- [x] Tag the immutable paper artifact as `v1.0.0`.
- [x] Create a GitHub release and, if desired, archive that release with Zenodo.
