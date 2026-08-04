"""Recall-over-required-fields: a second, reported score (Task 2).

Recall = |matched fields that are the schema's required (writable) fields| /
|required (writable) fields|. It is reported per candidate alongside precision;
it does NOT change the match decision (that still runs on precision).
"""

from engine.detect import MATCH_THRESHOLD, match_template


def _schema(path, fields):
    """fields: list of (name, required)."""
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": r, "locked": False, "is_formula": False}
            for n, r in fields
        ],
    }


def _ev(*names):
    return [{"field": n, "value": f"v_{n}"} for n in names]


def test_all_required_but_few_overall_scores_high_recall_low_precision():
    schema = _schema(
        ["C"],
        [("Brand", True), ("Model", True),
         ("Extra1", False), ("Extra2", False), ("Extra3", False)],
    )
    # Both required fields present, plus 3 unrelated noise fields.
    best, conf, cands = match_template(
        _ev("Brand", "Model", "noise1", "noise2", "noise3"), [schema]
    )
    c = cands[0]
    assert c.recall == 1.0                      # every required field covered
    assert c.score == 2 / 5                     # precision: 2 of 5 evidence map
    assert conf < MATCH_THRESHOLD               # precision alone says "no match"
    assert best is None                         # decision unchanged (precision-based)
    assert set(c.required_present) == {"Brand", "Model"}
    assert c.required_missing == []


def test_many_fields_but_few_required_scores_low_recall_decent_precision():
    schema = _schema(
        ["C"],
        [("Brand", True), ("Model", True), ("Voltage", True),
         ("Weight", False), ("Color", False)],
    )
    # All evidence maps (precision high) but only 1 of 3 required is present.
    best, _conf, cands = match_template(_ev("Weight", "Color", "Brand"), [schema])
    c = cands[0]
    assert c.score == 1.0                        # precision: all 3 evidence map
    assert best is not None                      # precision clears threshold
    assert c.recall == 1 / 3                     # only 1 of 3 required present
    assert set(c.required_present) == {"Brand"}
    assert set(c.required_missing) == {"Model", "Voltage"}


def test_no_required_fields_reports_recall_zero_by_convention():
    schema = _schema(["C"], [("A", False), ("B", False)])
    _best, _conf, cands = match_template(_ev("A"), [schema])
    # No required fields -> recall has no denominator; reported as 0.0.
    assert cands[0].recall == 0.0
    assert cands[0].required_present == []
    assert cands[0].required_missing == []
