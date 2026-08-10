"""metadata_fallback_rows and its wiring into build_pack_from_fields: page
metadata fills name/description ONLY when JSON-LD has neither, and only
ever enriches a page that already qualifies via JSON-LD or a real spec
table -- it never opens the "is this capturable" gate by itself."""

from scraper.assemble import (
    CONFIDENCE_LOOSE,
    build_pack_from_fields,
    metadata_fallback_rows,
)

SPEC_TABLE_HTML = """
<html><head>
  <title>Aluminium Bullnose Tile Trim | TBK Metal</title>
  <meta property="og:title" content="Aluminium Bullnose Tile Trim">
  <meta property="og:description" content="Real anodised aluminium tile edge trim.">
  <meta property="og:image" content="/img/bullnose.jpg">
</head><body>
<table><tr><th>Material</th><td>Aluminium</td></tr></table>
</body></html>
"""

NO_PRODUCT_SIGNAL_HTML = """
<html><head>
  <title>About Us | TBK Metal</title>
  <meta name="description" content="Learn about our company history.">
</head><body>no table, no json-ld here</body></html>
"""


def test_metadata_fallback_rows_fills_both_when_jsonld_has_neither():
    rows = metadata_fallback_rows(
        {}, {"name": "Widget", "description": "A widget."}, "https://ex.com/p", record_id="P1"
    )
    by = {r.field: r for r in rows}
    assert by["name"].value == "Widget"
    assert by["description"].value == "A widget."
    assert all(r.confidence == CONFIDENCE_LOOSE for r in rows)
    assert all(r.method == "scrape" and r.source_uri == "https://ex.com/p" for r in rows)


def test_metadata_fallback_rows_never_overrides_jsonld_name():
    rows = metadata_fallback_rows(
        {"name": "Real JSON-LD Name"}, {"name": "Metadata Name", "description": "Meta desc"},
        "https://ex.com/p", record_id="P1",
    )
    fields_present = {r.field for r in rows}
    assert "name" not in fields_present  # JSON-LD already had it -- not duplicated/overridden
    assert "description" in fields_present


def test_metadata_fallback_rows_empty_when_metadata_has_nothing_new():
    assert metadata_fallback_rows({"name": "X", "description": "Y"}, {}, "https://ex.com/p", record_id="P1") == []


def test_build_pack_adds_metadata_rows_to_a_real_spec_table_page(tmp_path):
    # The actual root-cause fix: a real product page (has a spec table) with
    # NO JSON-LD now gets name/description from its own page metadata.
    out = tmp_path / "p.bkpack.zip"
    rows = build_pack_from_fields(
        {}, "https://ex.com/p", str(out), schemas=[], page_html=SPEC_TABLE_HTML
    )
    by = {r.field: r for r in rows}
    assert by["name"].value == "Aluminium Bullnose Tile Trim"  # og:title, not the noisier <title>
    assert by["description"].value == "Real anodised aluminium tile edge trim."
    assert by["name"].confidence == CONFIDENCE_LOOSE
    assert "Material" in by  # existing spec-table row untouched


def test_build_pack_metadata_never_overrides_real_jsonld_name(tmp_path):
    fields = {"name": "Real JSON-LD Product Name"}
    out = tmp_path / "p2.bkpack.zip"
    rows = build_pack_from_fields(
        fields, "https://ex.com/p", str(out), schemas=[], page_html=SPEC_TABLE_HTML
    )
    by = {r.field: r for r in rows}
    assert by["name"].value == "Real JSON-LD Product Name"
    assert by["name"].confidence != CONFIDENCE_LOOSE


def test_build_pack_metadata_alone_does_not_open_the_capture_gate(tmp_path):
    # A page with real title/meta tags but NEITHER JSON-LD NOR a spec table
    # (a blog/about page, not a product) must still yield nothing -- SEO
    # metadata exists on almost every real page and must never by itself
    # make a non-product page look capturable.
    out = tmp_path / "about.bkpack.zip"
    rows = build_pack_from_fields(
        {}, "https://ex.com/about", str(out), schemas=[], page_html=NO_PRODUCT_SIGNAL_HTML
    )
    assert rows == []
    assert not out.exists()
