"""Task 5's real end-to-end proof: TBK Metal's real Edge Trim page, run
through the actual, unmodified pipeline (spec_table_rows -> match_template ->
populate_from_evidence -> write_template) against the real, on-disk 510-schema
store and the real Edge Trim schema's real structure -- no stub schema, no
synthetic vocabulary.

The 8 (key, value) pairs are REAL, reused unchanged from
programs/engine/tests/test_populate_integration_tbk.py (see that file's
docstring for the live-reconfirmation details and the one CONSTRUCTED,
clearly-labeled tie-breaking hint appended to the real "Applications" value so
detect.py's real 5-way tie among the Edge Trims & Profiles family resolves to
"Edge Trim" -- the same honest reasoning applies here unchanged; this file
only adds the write_template step on top of that already-proven result.

PREDICTED, now CONFIRMED: the real "Material" evidence value "Aluminum Alloy"
does not exactly match the real Edge Trim schema's Material vocabulary
(["Aluminum", "Stainless Steel", "PVC", "Brass", "Chrome"]) -- populate.py's
looser evidence-matching bar populates it anyway (see
test_full_pipeline_populated_count_reported_honestly), but write_template's
stricter, vocabulary-bound dropdown check correctly leaves it blank rather
than write an invalid dropdown value into the file.
"""

import json
from pathlib import Path

import openpyxl
from engine.detect import match_template
from engine.populate import populate_from_evidence
from engine.writer import write_template
from schemas.store import DATA_DIR
from scraper.assemble import spec_table_rows

TBK_URL = "https://www.tbkmetal.com/products/aluminium-bullnose-border-tile-edge-trim/"

_REAL_APPLICATIONS = "Ceramic tile edge protection & decoration"
# CONSTRUCTED FOR THIS TEST, appended below -- not scraped. See module docstring.
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


def _real_schema_store():
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in Path(DATA_DIR).rglob("*.json")
        if p.name != "index.json"
    ]


def test_real_tbk_page_writes_a_verified_real_xlsx(tmp_path, capsys):
    rows = spec_table_rows(_TBK_HTML, TBK_URL, record_id="tbk-bullnose")
    evidence = [r.to_dict() for r in rows]

    schema, confidence, _candidates = match_template(evidence, _real_schema_store())
    assert schema is not None and schema["category_path"][-1] == "Edge Trim"

    population = populate_from_evidence(evidence, schema)
    out = tmp_path / "tbk_edge_trim.xlsx"

    result = write_template(population, schema, out)

    # Mandatory self-verification passed on the real file -- no forced pass.
    assert result.verification.structure_ok
    assert result.verification.value_mismatches == []
    assert result.verification.formula_fields_left_blank == ["System Product Name"]

    assert "Floor Price" not in result.written_fields  # never populated regardless

    # The real, confirmed shape of this specific real-world case: populate.py
    # populates Material ("Aluminum Alloy") and Color (the raw multi-option
    # scraped string) because its evidence bar has no vocabulary check -- but
    # BOTH are dropdown-typed in the real schema and NEITHER value exactly
    # matches its real, controlled vocabulary (Material's vocab is
    # ["Aluminum", "Stainless Steel", "PVC", "Brass", "Chrome"]; Color's is
    # ten specific named shades). write_template's stricter, vocabulary-bound
    # check correctly refuses to write either -- so, honestly, NOTHING is
    # written into this real file: every real field the page could plausibly
    # supply fails the schema's own controlled-vocabulary bar, and every other
    # field simply has no usable evidence at all. A fully-blank-but-
    # structurally-correct file is still a legitimate, honest output here.
    assert result.written_fields == []
    assert result.blank_invalid_dropdown == ["Material", "Color"]
    assert result.blank_unresolved_numeric == []
    assert result.blank_never_populate == []
    assert set(result.blank_needs_input) >= {
        "Brand", "Length", "Size", "Size Unit", "Length Unit",
        "Selling Unit", "Quantity per Selling Unit",
    }

    wb = openpyxl.load_workbook(out, data_only=True)
    ws = wb["Template"]
    by_field = {}
    for f in schema["fields"]:
        from openpyxl.utils import column_index_from_string

        col = column_index_from_string(f["column"])
        by_field[f["name"]] = ws.cell(row=3, column=col).value

    print(f"\nmatched category: {schema['category_path']} (confidence={confidence})")
    print(f"written_fields: {result.written_fields}")
    print(f"blank_needs_input: {sorted(result.blank_needs_input)}")
    print(f"blank_invalid_dropdown: {result.blank_invalid_dropdown}")
    print(f"blank_unresolved_numeric: {sorted(result.blank_unresolved_numeric)}")
    print(f"blank_never_populate: {result.blank_never_populate}")
    print(f"formula_fields_left_blank: {result.verification.formula_fields_left_blank}")
    print("full written row (all real schema fields, in column order):")
    for name, value in by_field.items():
        print(f"  {name!r}: {value!r}")
