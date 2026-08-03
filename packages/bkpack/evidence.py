"""
Evidence Ledger — the runtime enforcement of BK's one non-negotiable rule:
'no evidence, no value'.

Every product field is in exactly one of two states:
  (a) a value, backed by a source_uri it was read from — absence=False
  (b) explicitly confirmed NOT present in any source — absence=True, value=None

There is no third state. A field cannot be silently blank, and a field
cannot carry a value with nothing to point to. EvidenceRow raises on
construction if a row violates this — so a bad row can never even be
built, let alone published.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional
import json
import time


def validate_row_dict(row: dict) -> list[str]:
    """Pure function: check one evidence row dict for internal consistency.
    Used both by EvidenceRow (write-time) and validator.py (read-time, on
    raw bytes from disk) — so a hand-edited or corrupted pack is caught
    independently of whether it went through this library at all.
    Returns a list of problems; empty list = valid.
    """
    problems = []
    record_id = row.get("record_id")
    field_name = row.get("field")
    absence = bool(row.get("absence", False))
    value = row.get("value")
    source_uri = row.get("source_uri")

    if absence and value is not None:
        problems.append(
            f"{record_id}.{field_name}: marked absence=True but has a "
            f"non-null value ({value!r}) — contradictory."
        )
    if not absence and value is None:
        problems.append(
            f"{record_id}.{field_name}: value is null but absence is not "
            f"True — a field must be a real sourced value or an explicit "
            f"confirmed absence, never a silent blank."
        )
    if not absence and value is not None and not source_uri:
        problems.append(
            f"{record_id}.{field_name} = {value!r} has no source_uri — "
            f"every value must be traceable to where it came from."
        )
    return problems


@dataclass
class EvidenceRow:
    record_id: str
    field: str
    value: Optional[str]
    source_uri: Optional[str]
    method: str  # "scrape" | "pdf" | "field-capture" | "manual"
    confidence: float
    absence: bool = False
    ts: float = field(default_factory=time.time)

    def __post_init__(self):
        problems = validate_row_dict(asdict(self))
        if problems:
            raise ValueError("Invalid EvidenceRow — " + "; ".join(problems))

    def to_dict(self) -> dict:
        return asdict(self)


def write_evidence_jsonl(rows: list[EvidenceRow]) -> str:
    lines = [json.dumps(r.to_dict()) for r in rows]
    return "\n".join(lines) + ("\n" if lines else "")


def read_evidence_jsonl(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]
