"""The combined decision rule (Task 3): a candidate is only ACCEPTED as the match
if precision AND recall both clear their bars — unless the schema declares no
required fields at all (gate inapplicable; precision alone still governs, which
preserves the pre-existing recall==0.0-by-convention behaviour for such schemas).

Grounded in the real TBK Metal Edge Trim diagnostic: precision alone picked
"Decorative PVC Panels" (precision=0.625, but only 5 of its 18 required fields
covered -> recall=0.278) over the genuinely correct "Edge Trim" (precision=0.500,
4 of 7 required fields covered -> recall=0.571). classify_category was evaluated
too and found uninformative on that real page (product_text was empty -> every
schema scored 0.0, a pure tie) so it is NOT part of this rule.
"""

from engine.detect import MATCH_THRESHOLD, RECALL_THRESHOLD, match_template


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


def test_precision_misleads_recall_corrects_like_the_tbk_case():
    # WRONG: broad/shallow overlap gives high precision, but most of its OWN
    # required fields are uncovered (mirrors Decorative PVC Panels: 0.625/0.278).
    wrong = _schema(
        ["Wrong"],
        [(n, True) for n in ("A", "B", "C", "X", "Y", "Z", "W", "V")],
    )
    # CORRECT: fewer of the evidence fields map to it (lower precision), but the
    # required fields it DOES have are (mostly) covered (mirrors Edge Trim: 0.500/0.571).
    correct = _schema(["Correct"], [("A", True), ("B", True)])

    evidence = _ev("A", "B", "C", "D")  # C, D don't map to either schema
    best, conf, cands = match_template(evidence, [wrong, correct])

    wrong_cand = next(c for c in cands if c.category_path == ["Wrong"])
    correct_cand = next(c for c in cands if c.category_path == ["Correct"])
    assert wrong_cand.score == 0.75 and wrong_cand.recall == 3 / 8   # high precision, fails recall
    assert correct_cand.score == 0.5 and correct_cand.recall == 1.0  # lower precision, clears recall

    # Old (precision-only) behaviour would have picked "Wrong" (0.75 > 0.5).
    assert cands[0].category_path == ["Wrong"]  # candidates stay precision-sorted (transparency)
    # The new combined rule correctly picks "Correct" instead.
    assert best is not None
    assert best["category_path"] == ["Correct"]
    assert conf == 0.5  # confidence reflects the ACCEPTED candidate's precision


def test_obvious_agreement_case_is_not_regressed():
    schema = _schema(["Obvious"], [("A", True), ("B", True)])
    best, conf, cands = match_template(_ev("A", "B"), [schema])

    assert cands[0].score == 1.0 and cands[0].recall == 1.0
    assert best is not None
    assert best["category_path"] == ["Obvious"]
    assert conf == 1.0


def test_no_required_fields_declared_gate_is_inapplicable():
    # A schema that marks nothing required has no recall denominator (0.0 by
    # convention). The gate must not block it -- precision alone still governs,
    # exactly as before this task.
    schema = _schema(["NoRequired"], [("A", False), ("B", False)])
    best, conf, cands = match_template(_ev("A", "B"), [schema])

    assert cands[0].recall == 0.0
    assert cands[0].required_present == []
    assert cands[0].required_missing == []
    assert best is not None  # NOT blocked despite recall==0.0
    assert conf == 1.0


def test_gate_rejects_when_no_candidate_clears_both_bars():
    # Only the "wrong" shape exists (no correct alternative) -> honestly no match.
    wrong = _schema(["Wrong"], [(n, True) for n in ("A", "B", "C", "X", "Y", "Z", "W", "V")])
    best, conf, cands = match_template(_ev("A", "B", "C", "D"), [wrong])

    assert cands[0].score == 0.75 >= MATCH_THRESHOLD
    assert cands[0].recall == 3 / 8 < RECALL_THRESHOLD
    assert best is None                 # precision alone is not enough
    assert conf == 0.75                 # still reports the top precision for visibility


def test_recall_threshold_equals_match_threshold_and_is_named():
    # Documents the grounding: the same "majority" bar (0.5) applied to a
    # different signal, not two independently-tuned magic numbers.
    assert RECALL_THRESHOLD == MATCH_THRESHOLD
