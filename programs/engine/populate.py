"""Populate a matched schema's writable fields from BK-PACK evidence.

A field with matching evidence is populated; a field without is marked
needs_input (never a silent blank, never fabricated). The overall status is
ready_for_review only when every *required* writable field has a value.

An evidence field that isn't a DIRECT name match may still populate via
schemas.aliases.resolve_field — the same category-aware, value-guarded
mechanism engine/detect.py's _score() uses for scoring (e.g. "Height" -> an
Edge Trim's "Size"). A direct match's bar is unchanged: whatever raw value
evidence provides populates, exactly as before. An ALIAS-resolved match to a
NUMERIC field gets one extra check (_is_confirmed_numeric, via
common/units.py's normalize_value): the value must resolve to one specific
measurement, not a multi-option/categorical passthrough like "8/10/12mm" —
which the aliases.py guard itself already accepts (see aliases.py's
docstring), so without this extra check it would wrongly populate. The alias
resolved correctly in that case; the value itself just isn't one specific,
writable answer. A non-numeric alias target (Brand, Grade, Color, ...) is not
subject to this extra check — resolve_field's own guard is the only bar for
it, same as detect.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.units import normalize_value
from schemas.aliases import resolve_field

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


def _is_confirmed_numeric(value: str) -> bool:
    """True if common/units.py's normalize_value resolves this to ONE specific
    measurement — a scalar with a real unit — rather than a multi-axis list
    ("300 x 600 mm") or an unresolved categorical/multi-option passthrough
    ("8/10/12mm", which aliases.py's own single_axis_length guard accepts, so
    this is the check that keeps it from being treated as a confirmed value).

    Scope: only meaningful for a NUMERIC target field reached via alias
    resolution (see populate_from_evidence) — a length-shaped value is what
    this is evaluating. It is not applied to non-numeric fields (Brand, Grade,
    Color, ...), since normalize_value only understands length units; a
    genuinely single non-numeric value (e.g. a brand name) is not put through
    this check at all.
    """
    normalized, unit, _confidence = normalize_value(value)
    return unit is not None and not isinstance(normalized, list)


def _evidence_value_map(bkpack_evidence, writable_canon, available_fields) -> dict:
    """canonical schema field name -> (first non-blank value seen, was_aliased).

    A blank value is NOT evidence of a real value — it must not populate a field
    (that would be the silent blank this project forbids), so such rows are
    skipped and the field falls through to needs_input.

    Each evidence field name is first checked for a DIRECT canonical match
    against the schema's own writable fields (writable_canon); only when there
    is no direct match is it resolved via schemas.aliases.resolve_field — the
    same category-aware, value-guarded mechanism engine/detect.py's _score()
    uses. ``was_aliased`` records which path found it, so
    populate_from_evidence can apply the extra numeric-confirmation check only
    to the alias path (see _is_confirmed_numeric) — a direct match's bar is
    unchanged.
    """
    values: dict[str, tuple[str, bool]] = {}
    for row in bkpack_evidence:
        if row.get("absence"):
            continue
        name = row.get("field")
        value = row.get("value")
        if not name or _is_blank(value):
            continue
        base_canon = canonical(name)
        target = base_canon
        aliased = False
        if base_canon not in writable_canon:
            resolved_name = resolve_field(base_canon, value, available_fields=available_fields)
            target = canonical(resolved_name)
            aliased = target != base_canon
        values.setdefault(target, (str(value), aliased))
    return values


def populate_from_evidence(bkpack_evidence, schema) -> PopulationResult:
    fields = writable_fields(schema)
    writable_canon = {canonical(f["name"]): f["name"] for f in fields}
    available = set(writable_canon.values())
    values = _evidence_value_map(bkpack_evidence, writable_canon, available)
    results: list[FieldResult] = []
    missing_required: list[str] = []
    populated = 0

    for f in fields:
        name = f["name"]
        required = bool(f.get("required"))
        canon = canonical(name)
        entry = values.get(canon)
        if entry is not None:
            value, was_aliased = entry
            if was_aliased and f.get("type") == "numeric" and not _is_confirmed_numeric(value):
                entry = None  # aliased correctly, but not one confirmed value
        if entry is not None:
            value, _was_aliased = entry
            results.append(
                FieldResult(name=name, required=required, status="populated", value=value)
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
