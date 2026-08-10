"""populate_from_evidence's numeric multi-option handling: a real "/"-
separated stocked-size list (via common.units.parse_multi_option_numeric)
becomes a reported variant_candidate, the same discipline as a multi-option
dropdown value -- never a guessed single number, never silently dropped."""

from engine.populate import populate_from_evidence


def _numeric_schema(*, required=True):
    return {
        "category_path": ["Cat"],
        "fields": [
            {"name": "Length", "type": "numeric", "required": required,
             "locked": False, "is_formula": False},
        ],
    }


def _ev(value):
    return [{"field": "Length", "value": value, "absence": False}]


def test_multi_option_numeric_becomes_variant_candidate():
    result = populate_from_evidence(_ev("2.4/2.5/2.7/3 Meters"), _numeric_schema())
    f = result.fields[0]
    assert f.status == "variant_candidate"
    assert f.value is None
    assert f.candidates == ["2.4 Meters", "2.5 Meters", "2.7 Meters", "3.0 Meters"]
    assert f.reason == "multi_option_numeric"


def test_single_confirmed_number_still_populates_normally():
    result = populate_from_evidence(_ev("2.5 m"), _numeric_schema())
    f = result.fields[0]
    assert f.status == "populated"
    assert f.value == "2.5 m"


def test_genuinely_unresolvable_numeric_value_stays_needs_input():
    # Multi-axis ("x"-separated) is neither a single confirmed number nor a
    # parseable multi-option list -- stays plain needs_input, not variant_candidate.
    result = populate_from_evidence(_ev("300 x 600 mm"), _numeric_schema())
    f = result.fields[0]
    assert f.status == "needs_input"
    assert f.reason == "not_one_confirmed_number"
    assert f.candidates == []


def test_variant_candidate_required_numeric_field_blocks_ready_for_review():
    result = populate_from_evidence(_ev("2.4/2.5/2.7/3 Meters"), _numeric_schema(required=True))
    assert result.status == "incomplete"
    assert result.missing_required == ["Length"]
    assert result.populated_count == 0


def test_variant_candidate_optional_numeric_field_does_not_block_ready_for_review():
    result = populate_from_evidence(_ev("2.4/2.5/2.7/3 Meters"), _numeric_schema(required=False))
    assert result.status == "ready_for_review"
    assert result.missing_required == []
