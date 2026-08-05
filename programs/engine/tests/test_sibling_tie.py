"""Sibling tie-break against the REAL on-disk 8mm/10mm/12mm TMT schemas.

The schemas are real; the evidence in these tests is clearly constructed for the
test (not scraped), to exercise the exact-match / no-match / ambiguous cases.
"""

import json
from pathlib import Path

from engine.detect import Candidate, match_template, resolve_sibling_tie
from schemas.store import DATA_DIR

_TMT_DIR = Path(DATA_DIR) / "Building Materials"
_SIBLINGS = ["8mm", "10mm", "12mm"]


def _load_sibling(size):
    p = _TMT_DIR / f"Steel_&_Reinforcements_-_High_Yield_Steel_Bars_(TMT_bars)_-_{size}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _tied_candidates():
    return [
        Candidate(category_path=_load_sibling(s)["category_path"], score=0.3, matched_fields=[])
        for s in _SIBLINGS
    ]


def test_exact_value_resolves_to_the_matching_sibling():
    resolved = resolve_sibling_tie(_tied_candidates(), {"diameter": "12 mm"})
    assert resolved is not None
    assert resolved.category_path[-1] == "12mm"


def test_value_matching_no_sibling_returns_none():
    assert resolve_sibling_tie(_tied_candidates(), {"diameter": "5 mm"}) is None


def test_value_matching_more_than_one_sibling_returns_none():
    # 8 mm and 12 mm each match a different sibling -> ambiguous -> unresolved.
    assert resolve_sibling_tie(_tied_candidates(), {"a": "8 mm", "b": "12 mm"}) is None


def test_unitless_value_does_not_resolve():
    # "12" with no unit is not a size (units.py never assumes one) -> no resolve.
    assert resolve_sibling_tie(_tied_candidates(), {"diameter": "12"}) is None


def test_match_template_breaks_top_tie_to_the_right_sibling():
    schemas = [_load_sibling(s) for s in _SIBLINGS]
    # Identical fields -> all three tie at top precision; the 12 mm diameter value
    # resolves the tie to the 12mm sibling. Material is added (a required field
    # common to all three siblings) so recall clears the combined decision rule's
    # gate (see test_recall_gate.py) without disturbing the precision tie.
    evidence = [
        {"field": "Grade", "value": "Fe500"},
        {"field": "Diameter", "value": "12 mm"},
        {"field": "Length", "value": "12 m"},
        {"field": "Material", "value": "TMT Steel"},
    ]
    best, _conf, cands = match_template(evidence, schemas)
    assert cands[0].category_path[-1] == "12mm"      # tie broken to the right one
    assert cands[0].score == cands[1].score          # genuinely equal precision
    assert best is not None and best["category_path"][-1] == "12mm"
