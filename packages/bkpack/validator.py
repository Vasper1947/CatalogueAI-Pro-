"""
The deterministic gate every BK-PACK must pass before Program 3 will touch
it. Checks structure, checksum integrity, and — the rule everything else
in this project depends on — that every evidence row is internally
consistent ('no evidence, no value').

Independent of the writer on purpose: every check here is re-derived from
the raw ZIP bytes, so a hand-edited, corrupted, or maliciously-crafted
pack cannot slip past just because it was never built by build_bkpack().
"""

import hashlib
import json
import sys
import zipfile
from dataclasses import dataclass, field

from .spec import REQUIRED_FILES
from .evidence import validate_row_dict


@dataclass
class ValidationReport:
    path: str
    ok: bool = True
    errors: list = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def print_report(self) -> None:
        print(f"[{'PASS' if self.ok else 'FAIL'}] {self.path}")
        for e in self.errors:
            print(f"  - {e}")


def validate_bkpack(path: str) -> ValidationReport:
    report = ValidationReport(path=path)
    try:
        zf = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, FileNotFoundError, OSError) as e:
        report.fail(f"not a readable ZIP: {e}")
        return report

    with zf:
        names = set(zf.namelist())

        missing = REQUIRED_FILES - names
        if missing:
            report.fail(f"missing required file(s): {sorted(missing)}")
            return report

        try:
            datapackage = json.loads(zf.read("datapackage.json"))
        except json.JSONDecodeError as e:
            report.fail(f"datapackage.json is not valid JSON: {e}")
            return report
        for key in ("bkpack_version", "producer", "product_count"):
            if key not in datapackage:
                report.fail(f"datapackage.json missing required key: {key!r}")

        manifest_text = zf.read("manifest-sha256.txt").decode("utf-8")
        for line in manifest_text.splitlines():
            if not line.strip():
                continue
            expected_hash, rel_path = line.split("  ", 1)
            if rel_path not in names:
                report.fail(f"manifest references missing file: {rel_path}")
                continue
            actual_hash = hashlib.sha256(zf.read(rel_path)).hexdigest()
            if actual_hash != expected_hash:
                report.fail(
                    f"checksum mismatch for {rel_path}: manifest says "
                    f"{expected_hash[:12]}…, actual is {actual_hash[:12]}…"
                )

        evidence_text = zf.read("evidence.jsonl").decode("utf-8")
        for i, raw in enumerate(raw for raw in evidence_text.splitlines() if raw.strip()):
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as e:
                report.fail(f"evidence.jsonl line {i}: invalid JSON: {e}")
                continue
            for problem in validate_row_dict(row):
                report.fail(f"evidence.jsonl line {i}: {problem}")

    return report


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m bkpack.validator <path-to-bkpack.zip>")
        return 2
    report = validate_bkpack(sys.argv[1])
    report.print_report()
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
