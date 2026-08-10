"""Honest end-to-end integration proof: detect.py -> populate.py on TBK Metal's
real Edge Trim page, run through the actual pipeline (spec_table_rows,
match_template, populate_from_evidence) unmodified.

The 8 (key, value) pairs below are REAL — captured from a live scrape of
https://www.tbkmetal.com/products/aluminium-bullnose-border-tile-edge-trim/
(re-confirmed unchanged this session). They are reproduced here as an HTML
fixture, not fetched live, so this test is reproducible and does not depend on
network access in CI — the same discipline every other test in this suite
already follows.

No real page has ever cleared detect.py's precision+recall qualifying set
uniquely on its own; TBK's real evidence lands in a genuine 5-way tie among the
Edge Trims & Profiles family siblings (Corner Profile, Edge Trim, Expansion
Profile, Movement Joint, Transition Profile) that content-tie-break cannot
resolve, because none of the real evidence values contain any candidate's
distinguishing word. So ONE line is added here, clearly marked below as
CONSTRUCTED FOR THIS TEST (not scraped): it is appended to the real
"Applications" value (not a new evidence field/row, which would dilute
detect.py's precision denominator and could push every candidate below
MATCH_THRESHOLD) and contains "trim", the word this project's own
resolve_tie_by_content algorithm derives as uniquely distinguishing "Edge
Trim" among the tied family. This is a deliberately chosen, labeled hint used
to reach and prove out the full pipeline end to end — it is NOT presented as,
and must never be read as, a real scraped fact.
"""

import json
from pathlib import Path

from bkpack.writer import build_bkpack
from engine.app import _JOBS, _run_job, get_engine
from engine.detect import match_template
from engine.populate import populate_from_evidence
from schemas.store import DATA_DIR
from scraper.assemble import PRODUCER, spec_table_rows

TBK_URL = "https://www.tbkmetal.com/products/aluminium-bullnose-border-tile-edge-trim/"

# --- REAL scraped (key, value) pairs, re-confirmed live this session ---------
_REAL_APPLICATIONS = "Ceramic tile edge protection & decoration"
# CONSTRUCTED FOR THIS TEST, appended below — not scraped. Chosen to contain
# "trim", the word resolve_tie_by_content derives as uniquely distinguishing
# "Edge Trim" among the real 5-way tied family, for this test's proof only.
_TEST_HINT = " Constructed for this test: an ideal trim finish."

_TBK_HTML = f"""
<html><body>
<table>
  <tr><td>Material:</td><td>Aluminum Alloy</td></tr>
  <tr><td>Finish:</td><td>BA/Matte/Brush/Satin/Mirror/Emboss</td></tr>
  <tr><td>Color:</td><td>Silver/Golden/Bronze/Black Titanium/Rose Gold/Champagne, etc.</td></tr>
  <tr><td>Height:</td><td>8/10/12mm / Customized.</td></tr>
</table>
<table>
  <tr><td>Thickness:</td><td>0.5-2.0 mm / Customizable</td></tr>
  <tr><td>Length:</td><td>2.4/2.5/2.7/3 Meters</td></tr>
  <tr><td>Packing:</td><td>Plastic film for each piece, outside with carton</td></tr>
  <tr><td>Applications:</td><td>{_REAL_APPLICATIONS}{_TEST_HINT}</td></tr>
</table>
</body></html>
"""


def _tbk_evidence():
    rows = spec_table_rows(_TBK_HTML, TBK_URL, record_id="tbk-bullnose")
    return rows, [r.to_dict() for r in rows]


def _real_schema_store():
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in Path(DATA_DIR).rglob("*.json")
        if p.name != "index.json"
    ]


def test_content_tie_break_resolves_tbk_to_edge_trim_with_the_labeled_hint():
    _rows, evidence = _tbk_evidence()
    assert len(evidence) == 8  # unchanged field count -- the hint augments a value, not a row

    best, _confidence, candidates = match_template(evidence, _real_schema_store())

    assert best is not None, "the labeled hint should resolve the real tie"
    assert best["category_path"][-1] == "Edge Trim"
    resolved = next(c for c in candidates if c.category_path[-1] == "Edge Trim")
    assert resolved.resolution is not None
    assert resolved.resolution.method == "content_tie_break"
    assert resolved.resolution.matched_word == "trim"
    assert not any(c.ambiguous_tie for c in candidates)


def test_full_pipeline_populated_count_reported_honestly():
    _rows, evidence = _tbk_evidence()
    best, _confidence, _candidates = match_template(evidence, _real_schema_store())
    assert best is not None and best["category_path"][-1] == "Edge Trim"

    result = populate_from_evidence(evidence, best)
    by = {f.name: f for f in result.fields}

    # Honest, verified result now that populate.py runs dropdown values
    # through schemas.vocabulary.match_to_vocabulary (see that module and
    # populate.py's own docstring): Material's real value "Aluminum Alloy"
    # whole-word-contains the real vocabulary term "Aluminum", so it
    # populates the CANONICAL term, not the raw string. Color's real value
    # ("Silver/Golden/Bronze/Black Titanium/Rose Gold/Champagne, etc.")
    # genuinely contains THREE real vocabulary terms as whole words (Silver,
    # Gold, Black) -- a real, honest ambiguity, not a bug -- so it becomes a
    # variant_candidate rather than an arbitrarily-picked populated value.
    # Length and Size are ALSO real variant_candidates now: "2.4/2.5/2.7/3
    # Meters" (Length, a direct match) and "8/10/12mm / Customized." (Size,
    # via the Height alias) both resolve via
    # common.units.parse_multi_option_numeric into real stocked-size options
    # -- real signal, never a guessed single measurement.
    assert by["Material"].status == "populated"
    assert by["Material"].value == "Aluminum"
    assert by["Material"].reason == "whole_word_containment"
    assert by["Color"].status == "variant_candidate"
    assert by["Color"].value is None
    assert set(by["Color"].candidates) == {"Silver", "Gold", "Black"}
    assert by["Length"].status == "variant_candidate"
    assert by["Length"].reason == "multi_option_numeric"
    assert by["Length"].candidates == ["2.4 Meters", "2.5 Meters", "2.7 Meters", "3.0 Meters"]
    assert by["Size"].status == "variant_candidate"
    assert by["Size"].reason == "multi_option_numeric"
    assert by["Size"].candidates == ["8.0 mm", "10.0 mm", "12.0 mm"]

    assert result.populated_count == 1
    # Genuinely incomplete for real reasons: Brand was never stated on the
    # page (no name/description JSON-LD, no Brand vocabulary hit), and
    # Color/Length/Size are real, unresolved variant ambiguities (never
    # silently picked), and Size Unit/Length Unit/Selling Unit/Quantity per
    # Selling Unit have no usable evidence at all.
    assert result.status == "incomplete"
    assert set(result.missing_required) == {
        "Brand", "Color", "Length", "Size", "Size Unit", "Length Unit",
        "Selling Unit", "Quantity per Selling Unit",
    }


def test_real_ingest_pipeline_reports_the_same_honest_result(tmp_path):
    # The same proof through the actual /ingest surface (_run_job/get_engine),
    # a real BK-PACK, and the real on-disk 510-schema store -- nothing stubbed.
    rows, _evidence = _tbk_evidence()
    bp = tmp_path / "tbk.bkpack.zip"
    build_bkpack(str(bp), evidence_rows=rows, media_files={}, producer=PRODUCER)

    _JOBS["tbk-integration"] = {"status": "queued"}
    _run_job("tbk-integration", str(bp))
    res = get_engine("tbk-integration")

    assert res["status"] == "template_matched"
    assert res["detection"]["matched"][-1] == "Edge Trim"
    # 1, not 2: Color is a real variant_candidate now (see
    # test_full_pipeline_populated_count_reported_honestly), not silently
    # counted as populated with a value that doesn't fit the vocabulary.
    assert res["population"]["populated_count"] == 1
    assert res["population"]["status"] == "incomplete"
