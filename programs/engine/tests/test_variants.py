"""expand_variants: one record with real multi-option fields -> N rows, one
real option per row, exactly one axis expanded even when several fields are
variant_candidate simultaneously -- never a cartesian product."""

from engine.populate import FieldResult, PopulationResult
from engine.variants import expand_variants


def _population(fields):
    """fields: list of FieldResult."""
    missing_required = [f.name for f in fields if f.required and f.status != "populated"]
    return PopulationResult(
        category_path=["Cat", "Widget"], fields=fields,
        status="incomplete" if missing_required else "ready_for_review",
        missing_required=missing_required,
        populated_count=sum(1 for f in fields if f.status == "populated"),
        needs_input_count=sum(1 for f in fields if f.status != "populated"),
    )


def test_no_variant_candidates_returns_the_result_unchanged():
    pop = _population([FieldResult(name="Brand", required=True, status="populated", value="Acme")])
    rows, report = expand_variants("P1", pop)
    assert rows == [pop]
    assert report.expanded_field is None
    assert report.option_count == 0


def test_single_variant_field_expands_into_n_rows():
    pop = _population([
        FieldResult(name="Brand", required=True, status="populated", value="Acme"),
        FieldResult(name="Color", required=True, status="variant_candidate",
                    candidates=["Silver", "Gold", "Bronze"]),
    ])
    rows, report = expand_variants("P1", pop)

    assert len(rows) == 3
    colors = [next(f.value for f in r.fields if f.name == "Color") for r in rows]
    assert colors == ["Silver", "Gold", "Bronze"]
    assert all(r.status == "ready_for_review" for r in rows)  # Color now populated on every row
    assert report.expanded_field == "Color"
    assert report.option_count == 3
    assert report.other_variant_fields == []


def test_other_fields_untouched_and_traceable_to_the_same_source():
    pop = _population([
        FieldResult(name="Brand", required=True, status="populated", value="Acme"),
        FieldResult(name="Color", required=True, status="variant_candidate",
                    candidates=["Silver", "Gold"]),
    ])
    rows, _report = expand_variants("P1", pop)
    for r in rows:
        brand = next(f for f in r.fields if f.name == "Brand")
        assert brand.value == "Acme"  # same source evidence, not touched


def test_expanded_field_reason_marks_variant_expansion():
    pop = _population([
        FieldResult(name="Color", required=False, status="variant_candidate",
                    candidates=["Silver", "Gold"]),
    ])
    rows, _report = expand_variants("P1", pop)
    for r in rows:
        color = next(f for f in r.fields if f.name == "Color")
        assert color.reason == "variant_expansion"
        assert color.status == "populated"


def test_multiple_variant_fields_expands_only_the_largest_axis():
    # Color has 3 options, Length has 2 -- Color (more options) expands;
    # Length stays flagged on every expanded row, never cartesian-multiplied.
    pop = _population([
        FieldResult(name="Color", required=True, status="variant_candidate",
                    candidates=["Silver", "Gold", "Bronze"]),
        FieldResult(name="Length", required=True, status="variant_candidate",
                    candidates=["2.4 Meters", "2.5 Meters"]),
    ])
    rows, report = expand_variants("P1", pop)

    assert len(rows) == 3  # NOT 3*2=6 -- never a cartesian product
    assert report.expanded_field == "Color"
    assert report.other_variant_fields == ["Length"]
    for r in rows:
        length = next(f for f in r.fields if f.name == "Length")
        assert length.status == "variant_candidate"  # still flagged, not resolved
        assert length.candidates == ["2.4 Meters", "2.5 Meters"]


def test_required_variant_field_expansion_clears_missing_required():
    pop = _population([
        FieldResult(name="Color", required=True, status="variant_candidate",
                    candidates=["Silver", "Gold"]),
    ])
    rows, _report = expand_variants("P1", pop)
    for r in rows:
        assert r.status == "ready_for_review"
        assert r.missing_required == []


def test_still_missing_required_field_after_expansion_stays_incomplete():
    pop = _population([
        FieldResult(name="Color", required=True, status="variant_candidate",
                    candidates=["Silver", "Gold"]),
        FieldResult(name="Brand", required=True, status="needs_input"),
    ])
    rows, _report = expand_variants("P1", pop)
    for r in rows:
        assert r.status == "incomplete"
        assert r.missing_required == ["Brand"]
