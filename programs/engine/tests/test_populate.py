"""Population tests (synthetic schemas, no disk)."""

from engine.populate import populate_from_evidence


def _schema(path, fields):
    # fields: list of (name, required)
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": r, "locked": False, "is_formula": False}
            for n, r in fields
        ],
    }


def _ev(mapping):
    return [{"field": k, "value": v, "absence": False} for k, v in mapping.items()]


def test_unmatched_field_is_needs_input_not_blank():
    schema = _schema(["Cat"], [("Brand", True), ("Colour", False)])
    result = populate_from_evidence(_ev({"Brand": "Bosch"}), schema)

    by = {f.name: f for f in result.fields}
    assert by["Brand"].status == "populated"
    assert by["Brand"].value == "Bosch"
    assert by["Colour"].status == "needs_input"
    assert by["Colour"].value is None  # never fabricated, never silently blank-as-done


def test_missing_required_is_incomplete_and_named():
    schema = _schema(["Cat"], [("Brand", True), ("Grade", True)])
    result = populate_from_evidence(_ev({"Brand": "Bosch"}), schema)

    assert result.status == "incomplete"
    assert result.missing_required == ["Grade"]


def test_all_required_present_is_ready_for_review():
    schema = _schema(["Cat"], [("Brand", True), ("Grade", True), ("Colour", False)])
    result = populate_from_evidence(_ev({"Brand": "Bosch", "Grade": "A"}), schema)

    assert result.status == "ready_for_review"
    assert result.missing_required == []
    # an optional field with no evidence is still needs_input, not blocking review
    assert any(f.name == "Colour" and f.status == "needs_input" for f in result.fields)


def test_blank_value_is_needs_input_not_a_silent_populated_blank():
    # A required field fed an empty/whitespace value must NOT count as populated,
    # and must not let the overall status become ready_for_review.
    schema = _schema(["Cat"], [("Brand", True), ("Grade", True)])
    result = populate_from_evidence(_ev({"Brand": "Bosch", "Grade": "   "}), schema)

    by = {f.name: f for f in result.fields}
    assert by["Grade"].status == "needs_input"
    assert by["Grade"].value is None
    assert result.status == "incomplete"
    assert result.missing_required == ["Grade"]


def test_floor_price_field_is_never_populated_by_the_engine():
    # Defense-in-depth: even if a schema carried a Floor Price column and evidence
    # supplied a value, the engine must never emit it — it is excluded entirely.
    schema = _schema(["Cat"], [("Brand", True), ("Floor Price", False)])
    result = populate_from_evidence(_ev({"Brand": "Bosch", "Floor Price": "9999"}), schema)

    assert all(f.name != "Floor Price" for f in result.fields)
    assert not any(f.value == "9999" for f in result.fields)
    assert result.status == "ready_for_review"  # Brand present; Floor Price not engine's job
