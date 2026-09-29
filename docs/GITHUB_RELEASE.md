# GitHub release procedure

## Recommended repository choice

Publish this directory as a new repository such as `qos-sec-paper-artifact`. This avoids mixing the clean paper release with the large, dirty working history in the development repository.

Do not push the current development working tree with `git add .`.

## Before initialization

Complete every blocking item in `docs/RELEASE_CHECKLIST.md`, especially:

- verify the approved MIT License and article DOI metadata;
- review the secret scan;
- confirm the reference validator and smoke reproduction.

## Initialize and review

```bash
git init -b main

git add .gitattributes .gitignore
git add README.md VALIDATION.md CITATION.cff LICENSE
git add pyproject.toml requirements.txt requirements-hardware.txt requirements-lock.txt
git add configs docs figures reference_results scripts src tests

git status --short
git diff --cached --stat
git diff --cached
```

Use the explicit paths above so that unexpected files are not staged.

## Commit and publish

```bash
git commit -m "release: publish paper reproducibility artifact"
git remote add origin https://github.com/jianliya/qos-sec-paper-artifact.git
git push -u origin main

git tag -a v1.0.0 -m "Paper artifact v1.0.0"
git push origin v1.0.0
```

Create a GitHub Release from `v1.0.0`. If a software DOI is desired, archive that immutable release with Zenodo and add the DOI badge and citation metadata in a follow-up release.

## If the existing qos-sec repository must be reused

Do not force-push over the existing `main` branch. Create a reviewed release branch first and decide explicitly whether to merge it, preserve development history in another branch, or publish this artifact as a separate repository.
