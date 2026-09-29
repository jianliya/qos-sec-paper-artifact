from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "figures", "reference_results"}
TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".md",
    ".toml",
    ".txt",
    ".csv",
    ".yml",
    ".yaml",
}
PATTERNS = {
    "credential assignment": re.compile(
        r"(?i)(token|api[_-]?key|password|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
}
ALLOWED_MARKERS = {"your-token", "your_token", "IBM_QUANTUM_TOKEN"}


def main() -> int:
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(marker in line for marker in ALLOWED_MARKERS):
                continue
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path.relative_to(ROOT), line_number, label))
    for path, line, label in findings:
        print(f"{path}:{line}: {label}")
    if findings:
        print(
            f"Review required: {len(findings)} possible secret match(es).",
            file=sys.stderr,
        )
        return 1
    print("No obvious plaintext credentials found in release-facing text files.")
    print("This does not replace a Git-history scan or credential revocation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
