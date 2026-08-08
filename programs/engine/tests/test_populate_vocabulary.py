"""populate_from_evidence's dropdown-vocabulary wiring (Tasks 2 & 3): a
determinate vocabulary match populates the canonical term; no match is
needs_input with a reason distinguishing "no evidence" from "off vocabulary";
a genuinely multi-option value becomes an unresolved variant_candidate,
listing every real matched term."""

from engine.populate import populate_from_evidence


def _dropdown_schema(vocabulary, *, required=True):
    return {
        "category_path": ["Cat"],
        "fields": [
            {
                "name": "Color", "type": "dropdown", "required": required,
                "locked": False, "is_formula": False, "vocabulary": vocabulary,
            },
        ],
    }


def _ev(field, value):
    return [{"field": field, "value": value, "absence": False}]


def test_dropdown_exact_match_populates_canonical_term():
    schema = _dropdown_schema(["Black", "White"])
    result = populate_from_evidence(_ev("Color", "Black"), schema)
    f = result.fields[0]
    assert (f.status, f.value, f.reason) == ("populated", "Black", "exact")
    assert result.populated_count == 1


def test_dropdown_whole_word_containment_populates_canonical_not_raw():
    schema = _dropdown_schema(["Aluminum", "PVC"])
    result = populate_from_evidence(_ev("Color", "Aluminum Alloy"), schema)
    f = result.fields[0]
    assert f.status == "populated"
    assert f.value == "Aluminum"  # canonical term, not the raw "Aluminum Alloy"
    assert f.reason == "whole_word_containment"


def test_dropdown_off_vocabulary_value_is_needs_input_not_in_vocabulary():
    schema = _dropdown_schema(["Black", "White"])
    result = populate_from_evidence(_ev("Color", "Chartreuse"), schema)
    f = result.fields[0]
    assert f.status == "needs_input"
    assert f.reason == "not_in_vocabulary"
    assert f.value is None
    assert result.missing_required == ["Color"]  # required, unpopulated


def test_dropdown_no_evidence_at_all_is_needs_input_no_evidence():
    schema = _dropdown_schema(["Black", "White"])
    result = populate_from_evidence([], schema)
    f = result.fields[0]
    assert f.status == "needs_input"
    assert f.reason == "no_evidence"


def test_no_evidence_and_off_vocabulary_are_distinguishable_not_identical():
    # The whole point of Task 2's reason field: these are different problems
    # and must not look the same downstream.
    off_vocab = populate_from_evidence(_ev("Color", "Chartreuse"), _dropdown_schema(["Black"])).fields[0]
    no_evidence = populate_from_evidence([], _dropdown_schema(["Black"])).fields[0]
    assert off_vocab.status == no_evidence.status == "needs_input"
    assert off_vocab.reason != no_evidence.reason
    assert {off_vocab.reason, no_evidence.reason} == {"not_in_vocabulary", "no_evidence"}


def test_multi_option_value_becomes_variant_candidate_not_a_guess():
    schema = _dropdown_schema(["Silver", "Gold", "Bronze", "Black"])
    result = populate_from_evidence(_ev("Color", "Silver/Golden/Bronze"), schema)
    f = result.fields[0]
    assert f.status == "variant_candidate"
    assert f.value is None  # never resolved by picking one
    assert set(f.candidates) == {"Silver", "Bronze"}
    assert f.reason == "whole_word_containment_ambiguous"


def test_variant_candidate_required_field_blocks_ready_for_review():
    schema = _dropdown_schema(["Silver", "Gold", "Bronze"], required=True)
    result = populate_from_evidence(_ev("Color", "Silver/Gold"), schema)
    assert result.status == "incomplete"
    assert result.missing_required == ["Color"]
    assert result.populated_count == 0


def test_variant_candidate_optional_field_does_not_block_ready_for_review():
    schema = _dropdown_schema(["Silver", "Gold", "Bronze"], required=False)
    result = populate_from_evidence(_ev("Color", "Silver/Gold"), schema)
    assert result.status == "ready_for_review"
    assert result.missing_required == []
    assert result.fields[0].status == "variant_candidate"


def test_dropdown_with_no_vocabulary_falls_back_to_direct_populate():
    # A dropdown-typed field with an empty/unresolved vocabulary (should not
    # occur in real parsed schemas, but must not crash) behaves like a plain
    # string field: any non-blank value populates verbatim.
    schema = _dropdown_schema([])
    result = populate_from_evidence(_ev("Color", "Whatever"), schema)
    f = result.fields[0]
    assert (f.status, f.value) == ("populated", "Whatever")


def test_plain_string_field_behavior_unchanged():
    schema = {
        "category_path": ["Cat"],
        "fields": [
            {"name": "Notes", "type": "string", "required": False,
             "locked": False, "is_formula": False},
        ],
    }
    result = populate_from_evidence(_ev("Notes", "Some free text"), schema)
    f = result.fields[0]
    assert (f.status, f.value, f.reason) == ("populated", "Some free text", None)
