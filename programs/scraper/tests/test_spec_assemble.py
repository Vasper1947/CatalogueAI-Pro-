"""Spec-table wiring tests: provenance, tiered confidence, mixed-unit rows."""

from bkpack.validator import validate_bkpack
from scraper.assemble import build_pack_from_fields, spec_table_rows

MIXED_UNITS_HTML = """
<table>
  <tr><th>Thickness</th><td>10 mm</td></tr>
  <tr><th>Depth</th><td>0.5 in</td></tr>
  <tr><th>Material</th><td>Aluminium</td></tr>
  <tr><th>Code</th><td>1,234</td></tr>
</table>
"""


def test_spec_rows_carry_provenance_and_tiered_confidence():
    rows = spec_table_rows(MIXED_UNITS_HTML, "https://ex.com/p", record_id="P1")
    by = {r.field: r for r in rows}

    # mixed mm + inch both normalized to the canonical unit (mm)
    assert by["Thickness"].value == "10 mm"
    assert by["Depth"].value == "12.7 mm"

    assert all(r.method == "scrape" for r in rows)
    assert all(r.source_uri == "https://ex.com/p" for r in rows)
    assert all(r.record_id == "P1" for r in rows)

    # clean spec values rank above JSON-LD (0.9); ambiguous value flagged low
    assert by["Thickness"].confidence == 0.95
    assert by["Material"].confidence == 0.95
    assert by["Code"].confidence == 0.4
    assert by["Code"].value == "1,234"  # original, not a guessed number


def test_no_spec_table_yields_no_rows():
    assert spec_table_rows("<div>no table here</div>", "https://ex.com/p", record_id="P1") == []


def test_build_pack_appends_spec_rows_when_html_given(tmp_path):
    fields = {"name": "Trim", "sku": "S1"}
    out = tmp_path / "p.bkpack.zip"
    rows = build_pack_from_fields(
        fields, "https://ex.com/p", str(out), schemas=[], page_html=MIXED_UNITS_HTML
    )
    assert validate_bkpack(str(out)).ok
    present = {r.field for r in rows}
    assert "name" in present  # existing JSON-LD row preserved
    assert "Thickness" in present and "Depth" in present  # spec rows appended


def test_build_pack_unchanged_without_html(tmp_path):
    fields = {"name": "Trim", "sku": "S1"}
    out = tmp_path / "p2.bkpack.zip"
    rows = build_pack_from_fields(fields, "https://ex.com/p", str(out), schemas=[])
    # no page_html and schemas=[] -> only the JSON-LD-derived rows, unchanged
    assert {r.field for r in rows} == {"name", "sku"}


def test_build_pack_stages_spec_rows_with_no_json_ld_at_all(tmp_path):
    # The actual fix: a page with real spec-table data but NO JSON-LD (e.g.
    # fields == {}, exactly TBK Metal's real shape) must stage that spec-table
    # data — not silently return nothing just because to_evidence_rows(fields)
    # is empty.
    out = tmp_path / "spec_only.bkpack.zip"
    rows = build_pack_from_fields(
        {}, "https://ex.com/p", str(out), schemas=[], page_html=MIXED_UNITS_HTML
    )
    assert validate_bkpack(str(out)).ok
    assert {r.field for r in rows} == {"Thickness", "Depth", "Material", "Code"}


def test_build_pack_stages_nothing_when_neither_source_has_data(tmp_path):
    # The one case the gate must still catch: no JSON-LD AND no real spec
    # table (an empty page, or one with only unrelated markup) -> no pack.
    out = tmp_path / "neither.bkpack.zip"
    rows = build_pack_from_fields(
        {}, "https://ex.com/p", str(out), schemas=[], page_html="<div>no table here</div>"
    )
    assert rows == []
    assert not out.exists()
