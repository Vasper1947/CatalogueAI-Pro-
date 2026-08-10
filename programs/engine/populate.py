"""Populate a matched schema's writable fields from BK-PACK evidence.

A field with matching evidence is populated; a field without is marked
needs_input (never a silent blank, never fabricated). The overall status is
ready_for_review only when every *required* writable field has a value.

An evidence field that isn't a DIRECT name match may still populate via
schemas.aliases.resolve_field — the same category-aware, value-guarded
mechanism engine/detect.py's _score() uses for scoring (e.g. "Height" -> an
Edge Trim's "Size").

Any match to a NUMERIC schema field — direct or aliased — gets one extra
check (_is_confirmed_numeric, via common/units.py's normalize_value): the
value must resolve to one specific measurement, not a multi-option/
categorical passthrough like "8/10/12mm" or "2.4/2.5/2.7/3 Meters". Whether a
value is actually one confirmed number doesn't depend on how its field name
was matched — a direct-match evidence field can state a multi-option spec
just as easily as an aliased one, and both are equally unconfirmed.

A match to a DROPDOWN schema field is run through
schemas.vocabulary.match_to_vocabulary against that field's real, controlled
vocabulary (see that module for the strictest-first matching rule). Three
outcomes, never collapsed into one:
  * a determinate match populates the CANONICAL vocabulary term (never the
    raw string), with FieldResult.reason recording which method matched —
    for auditability, same discipline as detect.py's tie resolutions.
  * no match at any level -> needs_input, FieldResult.reason="not_in_vocabulary"
    — deliberately distinct from FieldResult.reason="no_evidence" (a field
    with no evidence row at all). These are different problems: one has a
    real value that just doesn't fit the controlled list; the other has
    nothing. Collapsing them would hide which one a human needs to fix.
  * 2+ vocabulary terms present in the same raw value (e.g. a listing that
    genuinely offers "Silver/Golden/Bronze") -> status="variant_candidate",
    never resolved by picking one. FieldResult.candidates lists every
    matched term — real signal (one listing, N SKUs), recorded, not guessed
    away. Still contributes to missing_required if the field is required,
    since nothing was actually populated.

A non-dropdown, non-numeric field (plain string: Brand's free-text form,
Description, ...) keeps the original bar: any non-blank value populates,
verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from common.units import normalize_value, parse_multi_option_numeric
from schemas.aliases import resolve_field
from schemas.vocabulary import find_whole_word_matches, match_to_vocabulary

from engine.detect import canonical, writable_fields


@dataclass
class FieldResult:
    name: str
    required: bool
    status: str  # "populated" | "needs_input" | "variant_candidate"
    value: str | None = None
    # populated dropdown: the match_to_vocabulary method ("exact", "normalized", ...).
    # needs_input: "no_evidence" | "not_one_confirmed_number" | "not_in_vocabulary".
    # variant_candidate: the ambiguous method ("whole_word_containment_ambiguous", ...).
    # Anything else (plain string/numeric populated fields): None -- no method to report.
    reason: str | None = None
    # variant_candidate only: every vocabulary term found in the raw value.
    candidates: list[str] = field(default_factory=list)


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

    Scope: applied to every NUMERIC target field (see populate_from_evidence),
    regardless of whether it was reached by a direct name match or via alias —
    a length-shaped value is what this is evaluating, and that evaluation
    doesn't care how the field was found. It is not applied to non-numeric
    fields (Brand, Grade, Color, ...), since normalize_value only understands
    length units; a genuinely single non-numeric value (e.g. a brand name) is
    not put through this check at all.
    """
    normalized, unit, _confidence = normalize_value(value)
    return unit is not None and not isinstance(normalized, list)


def _evidence_value_map(bkpack_evidence, writable_canon, available_fields) -> dict:
    """canonical schema field name -> first non-blank value seen for it.

    A blank value is NOT evidence of a real value — it must not populate a field
    (that would be the silent blank this project forbids), so such rows are
    skipped and the field falls through to needs_input.

    Each evidence field name is first checked for a DIRECT canonical match
    against the schema's own writable fields (writable_canon); only when there
    is no direct match is it resolved via schemas.aliases.resolve_field — the
    same category-aware, value-guarded mechanism engine/detect.py's _score()
    uses.
    """
    values: dict[str, str] = {}
    for row in bkpack_evidence:
        if row.get("absence"):
            continue
        name = row.get("field")
        value = row.get("value")
        if not name or _is_blank(value):
            continue
        base_canon = canonical(name)
        target = base_canon
        if base_canon not in writable_canon:
            target = canonical(resolve_field(base_canon, value, available_fields=available_fields))
        values.setdefault(target, str(value))
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
        raw_value = values.get(canon)

        if raw_value is None:
            results.append(
                FieldResult(name=name, required=required, status="needs_input", reason="no_evidence")
            )
            if required:
                missing_required.append(name)
            continue

        if f.get("type") == "numeric":
            if _is_confirmed_numeric(raw_value):
                results.append(
                    FieldResult(name=name, required=required, status="populated", value=raw_value)
                )
                populated += 1
                continue
            multi_options = parse_multi_option_numeric(raw_value)
            if multi_options:
                # A real, recurring supplier pattern (e.g. "2.4/2.5/2.7/3
                # Meters") -- real signal, one listing, N stocked sizes, same
                # discipline as a multi-option dropdown value: never resolved
                # by picking one.
                results.append(
                    FieldResult(
                        name=name, required=required, status="variant_candidate",
                        reason="multi_option_numeric", candidates=multi_options,
                    )
                )
                if required:
                    missing_required.append(name)
                continue
            results.append(
                FieldResult(
                    name=name, required=required, status="needs_input",
                    reason="not_one_confirmed_number",
                )
            )
            if required:
                missing_required.append(name)
            continue

        if f.get("type") == "dropdown" and f.get("vocabulary"):
            vocab = f["vocabulary"]
            matched_term, method, _confidence = match_to_vocabulary(raw_value, vocab)
            if matched_term is not None:
                results.append(
                    FieldResult(
                        name=name, required=required, status="populated",
                        value=matched_term, reason=method,
                    )
                )
                populated += 1
                continue
            if method.endswith("_ambiguous"):
                candidates = find_whole_word_matches(raw_value, vocab)
                results.append(
                    FieldResult(
                        name=name, required=required, status="variant_candidate",
                        reason=method, candidates=candidates,
                    )
                )
                if required:
                    missing_required.append(name)
                continue
            results.append(
                FieldResult(
                    name=name, required=required, status="needs_input",
                    reason="not_in_vocabulary",
                )
            )
            if required:
                missing_required.append(name)
            continue

        # Plain string field (or a dropdown with no resolvable vocabulary):
        # the original bar -- any non-blank value populates, verbatim.
        results.append(
            FieldResult(name=name, required=required, status="populated", value=raw_value)
        )
        populated += 1

    status = "ready_for_review" if not missing_required else "incomplete"
    return PopulationResult(
        category_path=schema.get("category_path", []),
        fields=results,
        status=status,
        missing_required=missing_required,
        populated_count=populated,
        needs_input_count=len(results) - populated,
    )
