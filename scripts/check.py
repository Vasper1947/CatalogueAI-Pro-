"""Single checkpoint command: ruff, pytest, and a coverage report, one call.

Run before every commit (CLAUDE.md's "Definition of done"): `python scripts/check.py`.
Exits non-zero if ruff fails, any test fails, or total coverage drops below
COVERAGE_FLOOR -- so a regression is caught here, not discovered later.
"""

from __future__ import annotations

import subprocess
import sys

# The floor is the ACTUAL measured baseline at the time it was last set (see
# ROADMAP.md for the date/commit) -- never a round number picked in advance.
# It can only move up with a real coverage improvement, or down with an
# explicit, reasoned exception -- never silently.
# Set 2026-08-08: real measured total was 76.48%; floored to the integer
# below it so the check passes today and fails on any real regression.
COVERAGE_FLOOR = 76

# Actual top-level Python import names (packages/ and programs/ are just
# setuptools discovery directories, not real package namespaces -- there is
# no "packages.bkpack" to import, only "bkpack").
SOURCE_PACKAGES = [
    "bkpack",
    "common",
    "schemas",
    "domain_knowledge",
    "export",
    "scraper",
    "pdfworker",
    "engine",
]


def run(cmd: list[str], label: str) -> bool:
    print(f"\n{'=' * 20} {label} {'=' * 20}")
    result = subprocess.run(cmd, check=False)
    ok = result.returncode == 0
    print(f"--- {label}: {'PASS' if ok else 'FAIL'} ---")
    return ok


def main() -> int:
    ruff_ok = run(["python", "-m", "ruff", "check", "."], "ruff")

    cov_args = []
    for pkg in SOURCE_PACKAGES:
        cov_args += ["--cov=" + pkg]
    pytest_cmd = [
        "python", "-m", "pytest", "-q",
        *cov_args,
        "--cov-report=term-missing",
        f"--cov-fail-under={COVERAGE_FLOOR}",
    ]
    pytest_ok = run(pytest_cmd, f"pytest + coverage (floor {COVERAGE_FLOOR}%)")

    print(f"\n{'=' * 20} SUMMARY {'=' * 20}")
    print(f"ruff:              {'PASS' if ruff_ok else 'FAIL'}")
    print(f"pytest + coverage: {'PASS' if pytest_ok else 'FAIL'}")

    return 0 if (ruff_ok and pytest_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
