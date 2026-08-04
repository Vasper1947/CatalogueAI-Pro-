"""Grounded scoring adjustments (Task 2/3), justified by the real Task 1 data.

Two changes are implemented and tested here:
  (c) canonicalization hardening — strip extraction wrappers (<Grade>) and a
      trailing UNIT-only parenthetical ("Diameter (mm)"), so decorated spec
      field names match the schema field they clearly denote.
  (b) a deterministic denominator pre-filter — drop our own 'suggested_category'
      annotation and bare URL/email values, which structurally cannot be product
      spec attributes.

Confidence-weighting (option (a)) was evaluated on the real pages and REJECTED:
on vedantametalbazaar the decisive Diameter/Length fields carry the uncertain-
unit 0.40 tier, so weighting demotes exactly the fields that matter. It is
deliberately NOT implemented, so there is no test for it.
"""

from engine.detect import (
    _is_candidate_attribute,
    canonical,
    match_template,
)


def _schema(path, writable):
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": False, "locked": False, "is_formula": False}
            for n in writable
        ],
    }


# --- (c) canonicalization hardening ---------------------------------------


def test_canonical_strips_decorative_brackets_and_unit_parens():
    assert canonical("<Diameter (mm)>") == "diameter"
    assert canonical("<Length (meters)>") == "length"
    assert canonical("<Grade>") == "grade"
    assert canonical("Diameter(mm)") == "diameter"


def test_canonical_preserves_index_parenthetical_and_synonyms():
    # A parenthetical that is NOT a unit (an index) is part of the real name.
    assert canonical("Dimensions (1)") == "dimensions (1)"
    # Existing synonym behaviour is unchanged.
    assert canonical("title") == "name"
    assert canonical("cost") == "price"


def test_bracketed_spec_fields_now_match_schema():
    # This is the vedantametalbazaar shape: decorated names that scored 0 before.
    schema = _schema(
        ["Building Materials", "Steel & Reinforcements", "TMT bars", "12mm"],
        ["Diameter", "Length", "Grade", "Brand"],
    )
    evidence = [
        {"field": "<Diameter (mm)>", "value": "12"},
        {"field": "<Length (meters)>", "value": "12"},
        {"field": "<Grade>", "value": "Fe500D"},
        {"field": "<%C>", "value": "0.25 max"},  # a real spec, but not in schema
    ]
    _best, conf, cands = match_template(evidence, [schema])
    assert set(cands[0].matched_fields) == {"Diameter", "Length", "Grade"}
    assert conf == 3 / 4  # 3 of 4 distinct evidence fields map


# --- (b) denominator pre-filter -------------------------------------------


def test_prefilter_drops_annotation_and_urls_keeps_spec():
    assert _is_candidate_attribute("Diameter", "12 mm") is True
    assert _is_candidate_attribute("Grade", "Fe500") is True
    # our own classifier annotation is not a scraped product attribute
    assert _is_candidate_attribute("suggested_category", "A > B > C") is False
    # bare media URL / email are references, not spec attributes
    assert _is_candidate_attribute("image", "https://cdn.example.com/x.jpg") is False
    assert _is_candidate_attribute("contact", "sales@example.com") is False


def test_prefilter_raises_score_by_shrinking_denominator():
    schema = _schema(["C"], ["Diameter", "Grade"])
    evidence = [
        {"field": "Diameter", "value": "12 mm"},
        {"field": "Grade", "value": "Fe500"},
        {"field": "image", "value": "https://x/y.jpg"},  # dropped (url)
        {"field": "suggested_category", "value": "A > B"},  # dropped (annotation)
    ]
    best, conf, _cands = match_template(evidence, [schema])
    # denominator is the 2 real attributes, both match -> 1.0
    assert conf == 1.0
    assert best is not None
