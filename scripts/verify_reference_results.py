from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference_results"
SPEC = REFERENCE / "expected_metrics.json"


def nested(payload: object, path: list[str]) -> object:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            raise KeyError(f"cannot descend through {key!r} in {path!r}")
        current = current[key]
    return current


def close_at_reporting_precision(actual: float, expected: float, digits: int) -> bool:
    return round(actual, digits) == round(expected, digits)


def check_json(item: dict, digits: int) -> tuple[bool, str]:
    path = REFERENCE / item["file"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    actual = float(nested(payload, item["path"]))
    expected = float(item["expected"])
    ok = close_at_reporting_precision(actual, expected, digits)
    return ok, f"{item['name']}: actual={actual:.{digits}f}, expected={expected:.{digits}f}"


def check_csv(item: dict, digits: int) -> tuple[bool, str]:
    path = REFERENCE / item["file"]
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matches = [
        row
        for row in rows
        if all(row.get(key) == value for key, value in item["match"].items())
    ]
    if len(matches) != 1:
        return False, f"{item['name']}: expected one matching row, found {len(matches)}"
    actual = float(matches[0][item["column"]])
    expected = float(item["expected"])
    ok = close_at_reporting_precision(actual, expected, digits)
    return ok, f"{item['name']}: actual={actual:.{digits}f}, expected={expected:.{digits}f}"


def reference_digest() -> str:
    digest = hashlib.sha256()
    paths = (
        path
        for path in REFERENCE.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    )
    for path in sorted(paths):
        digest.update(path.relative_to(REFERENCE).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    digits = int(spec["reporting_precision"])
    failures = 0
    for item in spec["json_checks"]:
        ok, message = check_json(item, digits)
        print(("PASS" if ok else "FAIL") + "  " + message)
        failures += int(not ok)
    for item in spec["csv_checks"]:
        ok, message = check_csv(item, digits)
        print(("PASS" if ok else "FAIL") + "  " + message)
        failures += int(not ok)
    print(f"Reference tree digest: {reference_digest()}")
    if failures:
        print(
            f"Reference validation failed: {failures} check(s) did not match.",
            file=sys.stderr,
        )
        return 1
    print("Reference validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
