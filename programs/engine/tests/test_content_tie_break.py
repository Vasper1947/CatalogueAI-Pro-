"""Content-based tie disambiguation (Task 1/2): when resolve_sibling_tie's
numeric mechanism doesn't apply (shape-named siblings, not sized ones), try
each tied candidate's distinguishing leaf-name word(s) against the evidence
text — whole-word, case-insensitive, no fuzzy matching. Exactly one match
resolves the tie (reported: which word, in which field); zero or more than one
leaves it genuinely, explicitly tied — never a silent/arbitrary pick.
"""

from engine.detect import (
    Candidate,
    match_template,
    resolve_tie_by_content,
)


def _cand(path, score=0.5, recall=0.6):
    return Candidate(category_path=path, score=score, matched_fields=[], recall=recall)


FAMILY = ["Family", "Sub"]


def _tied(*leaves):
    return [_cand(FAMILY + [leaf]) for leaf in leaves]


def test_exactly_one_distinguishing_word_resolves_with_report():
    tied = _tied("Corner Profile", "Edge Trim", "Expansion Profile")
    resolved, resolution = resolve_tie_by_content(
        tied, {"applications": "used for a corner installation"}
    )
    assert resolved is not None
    assert resolved.category_path[-1] == "Corner Profile"
    assert resolution.method == "content_tie_break"
    assert resolution.matched_word == "corner"
    assert resolution.field == "applications"


def test_no_distinguishing_word_present_stays_tied():
    tied = _tied("Corner Profile", "Edge Trim", "Expansion Profile")
    resolved, resolution = resolve_tie_by_content(
        tied, {"applications": "used for general purposes"}
    )
    assert resolved is None
    assert resolution is None


def test_two_distinguishing_words_from_different_candidates_stays_tied():
    tied = _tied("Corner Profile", "Edge Trim", "Expansion Profile")
    resolved, resolution = resolve_tie_by_content(
        tied, {"applications": "corner and expansion joints"}
    )
    assert resolved is None
    assert resolution is None


def test_shared_family_prefix_word_is_never_distinguishing():
    # "trims" is part of the shared family prefix; a leaf word that EXACTLY
    # matches a prefix word (not just overlaps loosely) must be excluded.
    tied = [
        _cand(["Floor", "Tile Accessories", "Edge Trims & Profiles", "Corner Profile"]),
        _cand(["Floor", "Tile Accessories", "Edge Trims & Profiles", "Edge Trim"]),
    ]
    # Evidence literally says "edge" (matches the prefix word "edge") but that
    # must NOT resolve anything, since "edge" isn't distinguishing here.
    resolved, resolution = resolve_tie_by_content(tied, {"applications": "tile edge protection"})
    assert resolved is None
    assert resolution is None
    # "trim" (singular) is NOT in the prefix (which only has "trims", plural)
    # so it correctly remains distinguishing for Edge Trim.
    resolved, resolution = resolve_tie_by_content(tied, {"applications": "a clean trim look"})
    assert resolved is not None
    assert resolved.category_path[-1] == "Edge Trim"
    assert resolution.matched_word == "trim"


def test_word_shared_across_multiple_tied_leaves_is_not_distinguishing():
    # "Profile" appears in 2 of 3 leaves -> distinguishes neither.
    tied = _tied("Corner Profile", "Expansion Profile", "Movement Joint")
    resolved, resolution = resolve_tie_by_content(tied, {"applications": "a profile piece"})
    assert resolved is None
    assert resolution is None
    # "movement" is unique to the third leaf -> still resolvable.
    resolved, resolution = resolve_tie_by_content(tied, {"applications": "for movement control"})
    assert resolved is not None
    assert resolved.category_path[-1] == "Movement Joint"


def test_no_evidence_at_all_stays_tied():
    tied = _tied("Corner Profile", "Edge Trim")
    resolved, resolution = resolve_tie_by_content(tied, {})
    assert resolved is None
    assert resolution is None


def _schema(path, fields):
    """fields: list of (name, required)."""
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": r, "locked": False, "is_formula": False}
            for n, r in fields
        ],
    }


def _ev(mapping):
    return [{"field": k, "value": v} for k, v in mapping.items()]


def test_match_template_resolves_via_content_and_reports_resolution():
    # Two shape-named siblings, identical required-field shape (a genuine tie
    # resolve_sibling_tie's numeric mechanism can't touch), disambiguated by
    # evidence text mentioning one candidate's distinguishing word.
    corner = _schema(
        ["Family", "Sub", "Corner Profile"], [("Material", True), ("Length", True)]
    )
    edge = _schema(["Family", "Sub", "Edge Trim"], [("Material", True), ("Length", True)])
    evidence = _ev({
        "Material": "Aluminum",
        "Length": "2.5 m",
        "Applications": "a corner solution for tiles",
    })
    best, _conf, cands = match_template(evidence, [corner, edge])

    assert best is not None
    assert best["category_path"][-1] == "Corner Profile"
    assert cands[0].category_path[-1] == "Corner Profile"  # reordered to front
    assert cands[0].resolution is not None
    assert cands[0].resolution.method == "content_tie_break"
    assert cands[0].resolution.matched_word == "corner"
    assert not any(c.ambiguous_tie for c in cands)  # resolved, not ambiguous


def test_match_template_leaves_genuine_tie_explicit_never_silent():
    corner = _schema(
        ["Family", "Sub", "Corner Profile"], [("Material", True), ("Length", True)]
    )
    edge = _schema(["Family", "Sub", "Edge Trim"], [("Material", True), ("Length", True)])
    # No text distinguishing either candidate.
    evidence = _ev({"Material": "Aluminum", "Length": "2.5 m"})
    best, conf, cands = match_template(evidence, [corner, edge])

    assert best is None  # never an arbitrary pick
    assert conf == 1.0  # the tied precision, not silently 0 or a rejected higher tier
    tied = [c for c in cands if c.ambiguous_tie]
    assert len(tied) == 2
    assert {c.category_path[-1] for c in tied} == {"Corner Profile", "Edge Trim"}
