"""Multi-option field expansion: a record whose evidence genuinely offers
multiple options along one field (e.g. "Length: 2.4/2.5/2.7/3 Meters", or a
dropdown value like "Silver/Golden/Bronze") is real signal -- one listing, N
sellable variants -- not a value to guess down to one. expand_variants()
turns ONE PopulationResult with variant_candidate fields into N
PopulationResults, one real option per row, following BK's own stated
convention ("duplicate the row and vary the variant-specific field").

Only ONE axis expands per record, even when several fields are
variant_candidate simultaneously -- the field with the MOST options wins
(ties broken by field order, deterministic). Expanding more than one axis
would be a cartesian product across independent options, fabricating
combinations the supplier never actually stated together (e.g. "Silver,
2.4m" when the page never paired a specific color with a specific length).
The other variant_candidate fields on an expanded record stay flagged, not
silently resolved -- see VariantExpansion.other_variant_fields.

Every expanded row is fully traceable to its source: it is a copy of the
SAME source record's other fields (same evidence-derived values throughout),
with only the chosen axis field replaced by one of the real values the
source evidence actually stated -- reason="variant_expansion" marks exactly
which field was expanded and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.populate import FieldResult, PopulationResult


@dataclass
class VariantExpansion:
    """What expand_variants() decided for ONE source record -- reported
    explicitly, never a silent choice."""

    record_id: str
    expanded_field: str | None  # None if there was nothing to expand
    option_count: int = 0
    other_variant_fields: list[str] = field(default_factory=list)  # left flagged, not expanded


def _variant_candidate_fields(result: PopulationResult) -> list[FieldResult]:
    return [f for f in result.fields if f.status == "variant_candidate" and f.candidates]


def expand_variants(
    record_id: str, result: PopulationResult
) -> tuple[list[PopulationResult], VariantExpansion]:
    """Expand the single largest variant_candidate axis of one record's
    PopulationResult into N PopulationResults (one row per real option).
    Returns ([result], a no-op VariantExpansion) unchanged when there is
    nothing to expand.
    """
    candidate_fields = _variant_candidate_fields(result)
    if not candidate_fields:
        return [result], VariantExpansion(record_id=record_id, expanded_field=None)

    # Most options wins; ties broken by first-seen field order (deterministic,
    # never an arbitrary/random pick).
    chosen = max(candidate_fields, key=lambda f: len(f.candidates))
    other_names = [f.name for f in candidate_fields if f.name != chosen.name]

    expanded: list[PopulationResult] = []
    for option_value in chosen.candidates:
        new_fields = [
            FieldResult(
                name=f.name, required=f.required, status="populated",
                value=option_value, reason="variant_expansion",
            )
            if f.name == chosen.name
            else f
            for f in result.fields
        ]
        missing_required = [
            fr.name for fr in new_fields
            if fr.required and (fr.status != "populated" or fr.value is None)
        ]
        populated_count = sum(1 for fr in new_fields if fr.status == "populated")
        expanded.append(
            PopulationResult(
                category_path=result.category_path,
                fields=new_fields,
                status="ready_for_review" if not missing_required else "incomplete",
                missing_required=missing_required,
                populated_count=populated_count,
                needs_input_count=len(new_fields) - populated_count,
            )
        )

    return expanded, VariantExpansion(
        record_id=record_id, expanded_field=chosen.name,
        option_count=len(chosen.candidates), other_variant_fields=other_names,
    )
