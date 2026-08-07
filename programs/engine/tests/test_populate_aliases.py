"""populate_from_evidence now reuses schemas.aliases.resolve_field — the same
category-aware, value-guarded mechanism engine/detect.py's _score() already
uses — so a field arriving under an alias name gets a fair chance to populate.

This does NOT lower the bar for what counts as a confirmed value. ANY match to
a NUMERIC schema field — direct or aliased — gets one extra check beyond the
existing aliases.py guard: the value must resolve to one specific measurement
via common/units.py's normalize_value (a scalar with a real unit), not a
multi-option/categorical passthrough like "8/10/12mm" or "2.4/2.5/2.7/3
Meters" (the aliases.py single_axis_length guard already accepts a same-axis
option list like "8/10/12mm" — see aliases.py's own docstring — so without
this extra check an aliased match would wrongly populate; and a DIRECT match
can state a multi-option spec just as easily, so it gets the same scrutiny).
A non-numeric target (Brand, Grade, Color, ...) is unaffected by this extra
check, whether reached directly or via alias.
"""

from engine.populate import populate_from_evidence


def _schema(path, fields):
    """fields: list of (name, required, type)."""
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": r, "type": t, "locked": False, "is_formula": False}
            for n, r, t in fields
        ],
    }


def _ev(mapping):
    return [{"field": k, "value": v, "absence": False} for k, v in mapping.items()]


def _by_name(result):
    return {f.name: f for f in result.fields}


def test_aliased_single_unambiguous_value_now_populates():
    # "Height" is not a schema field name; it's an alias for "Size" (Edge Trim
    # family), guarded by single_axis_length. "10mm" is one clean measurement.
    schema = _schema(["Floor & Wall Finishes", "Edge Trim"], [
        ("Size", True, "numeric"),
        ("Length", True, "numeric"),
    ])
    result = populate_from_evidence(_ev({"Height": "10mm", "Length": "2.5 m"}), schema)

    by = _by_name(result)
    assert by["Size"].status == "populated"
    assert by["Size"].value == "10mm"  # sourced from the aliased evidence row
    assert by["Length"].status == "populated"


def test_aliased_multi_option_numeric_value_stays_needs_input_via_new_gate_not_never_attempted():
    # "Height: 8/10/12mm" passes the EXISTING aliases.py guard (single_axis_length
    # already accepts a same-axis option list) -- resolve_field DOES map it to
    # "Size". The NEW gate here is what still keeps it out: normalize_value
    # cannot resolve "8/10/12mm" to one specific scalar, so it is not a
    # confirmed value. A companion "Manufacturer" -> "Brand" alias (no guard,
    # non-numeric target) populates in the SAME call, proving resolution
    # genuinely ran for this evidence set -- Size's rejection is the new
    # value-confirmation gate, not resolve_field never being attempted.
    schema = _schema(["Floor & Wall Finishes", "Edge Trim"], [
        ("Size", True, "numeric"),
        ("Brand", True, "string"),
    ])
    result = populate_from_evidence(
        _ev({"Height": "8/10/12mm", "Manufacturer": "TBK Metal"}), schema
    )

    by = _by_name(result)
    assert by["Brand"].status == "populated"
    assert by["Brand"].value == "TBK Metal"  # proves resolve_field ran in this call
    assert by["Size"].status == "needs_input"
    assert by["Size"].value is None


def test_aliased_multi_axis_value_still_rejected_by_the_pre_existing_guard():
    # "Dimensions: 300 x 600 mm" is genuinely multi-axis -- the EXISTING
    # aliases.py guard (unaffected by this task) rejects it outright, so
    # resolve_field never maps it to "Diameter" at all. This is unchanged,
    # pre-existing behaviour, not the new normalize_value gate.
    schema = _schema(["Building Materials", "TMT"], [("Diameter", True, "numeric")])
    result = populate_from_evidence(_ev({"Dimensions": "300 x 600 mm"}), schema)

    by = _by_name(result)
    assert by["Diameter"].status == "needs_input"
    assert by["Diameter"].value is None


def test_direct_match_clean_single_value_still_populates():
    # A DIRECT name match with a genuinely single, clean value is unaffected --
    # the common case, no regression from adding the gate to direct matches.
    schema = _schema(["Floor & Wall Finishes", "Edge Trim"], [("Length", True, "numeric")])
    result = populate_from_evidence(_ev({"Length": "2.5 m"}), schema)

    by = _by_name(result)
    assert by["Length"].status == "populated"
    assert by["Length"].value == "2.5 m"


def test_direct_match_multi_option_value_now_also_rejected_by_the_gate():
    # A DIRECT name match (no aliasing involved) to a NUMERIC field is no
    # longer exempt: whether a value is one confirmed number doesn't depend on
    # how its field name was matched, so a direct-match multi-option spec is
    # rejected exactly like an aliased one would be.
    schema = _schema(["Floor & Wall Finishes", "Edge Trim"], [("Length", True, "numeric")])
    result = populate_from_evidence(_ev({"Length": "2.4/2.5/2.7/3 Meters"}), schema)

    by = _by_name(result)
    assert by["Length"].status == "needs_input"
    assert by["Length"].value is None
