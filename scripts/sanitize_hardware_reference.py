from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = (
    ROOT
    / "reference_results"
    / "results"
    / "hardware"
    / "timing_hardware_summary_ibm_kingston_6runs_2026-07-01_144002.json"
)


def scrub(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: scrub(item)
            for key, item in value.items()
            if key != "job_id"
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove provider job identifiers while preserving measurements."
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    before = args.path.read_text(encoding="utf-8").count('"job_id"')
    cleaned = scrub(payload)
    args.path.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    print(f"Removed {before} job_id field(s) from {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
