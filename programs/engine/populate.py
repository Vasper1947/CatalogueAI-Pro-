"""Populate a matched schema's writable fields from BK-PACK evidence.

A field with matching evidence is populated; a field without is marked
needs_input (never a silent blank, never fabricated). The overall status is
ready_for_review only when every *required* writable field has a value.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.detect import canonical, writable_fields


@dataclass
class FieldResult:
    name: str
    required: bool
    status: str  # "populated" | "needs_input"
    value: str | None = None


@dataclass
class PopulationResult:
    category_path: list
    fields: list  # list[FieldResult]
    status: str  # "ready_for_review" | "incomplete"
    missing_required: list
    populated_count: int
    needs_input_count: int


def _is_blank(value) -> bool:
    """True for values that carry no real content (must never populate a field).

    Covers None, empty/whitespace-only strings, and empty containers — the
    "silent blank" family this project forbids. A real 0/False is NOT blank.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _evidence_value_map(bkpack_evidence) -> dict:
    """canonical field name -> first non-blank value seen for it.

    A blank value is NOT evidence of a real value — it must not populate a field
    (that would be the silent blank this project forbids), so such rows are
    skipped and the field falls through to needs_input.
    """
    values: dict[str, str] = {}
    for row in bkpack_evidence:
        if row.get("absence"):
            continue
        name = row.get("field")
        value = row.get("value")
        if not name or _is_blank(value):
            continue
        values.setdefault(canonical(name), str(value))
    return values


def populate_from_evidence(bkpack_evidence, schema) -> PopulationResult:
    values = _evidence_value_map(bkpack_evidence)
    results: list[FieldResult] = []
    missing_required: list[str] = []
    populated = 0

    for f in writable_fields(schema):
        name = f["name"]
        required = bool(f.get("required"))
        canon = canonical(name)
        if canon in values:
            results.append(
                FieldResult(name=name, required=required, status="populated", value=values[canon])
            )
            populated += 1
        else:
            results.append(FieldResult(name=name, required=required, status="needs_input"))
            if required:
                missing_required.append(name)

    status = "ready_for_review" if not missing_required else "incomplete"
    return PopulationResult(
        category_path=schema.get("category_path", []),
        fields=results,
        status=status,
        missing_required=missing_required,
        populated_count=populated,
        needs_input_count=len(results) - populated,
    )
