"""extract_spec_table tests: two-column tables, definition lists, and misses."""

from scraper.discover import extract_spec_table

TABLE_HTML = """
<html><body>
<table>
  <tr><th>Material</th><td>Aluminium</td></tr>
  <tr><th>Width</th><td>10 mm</td></tr>
  <tr><th>Length</th><td>2.5 m</td></tr>
</table>
</body></html>
"""

DL_HTML = """
<html><body>
<dl>
  <dt>Colour</dt><dd>Silver</dd>
  <dt>Finish</dt><dd>Anodised</dd>
</dl>
</body></html>
"""

NO_TABLE_HTML = (
    "<html><body><div class='spec'>"
    "<span>Material</span><span>Aluminium</span></div></body></html>"
)


def test_two_column_table_extracts_all_pairs():
    assert extract_spec_table(TABLE_HTML) == [
        ("Material", "Aluminium"),
        ("Width", "10 mm"),
        ("Length", "2.5 m"),
    ]


def test_definition_list_extracts_pairs():
    assert extract_spec_table(DL_HTML) == [
        ("Colour", "Silver"),
        ("Finish", "Anodised"),
    ]


def test_no_table_or_dl_returns_empty_list():
    assert extract_spec_table(NO_TABLE_HTML) == []
    assert extract_spec_table("") == []


def test_wide_table_rows_are_ignored_only_two_column_kept():
    html = (
        "<table>"
        "<tr><td>a</td><td>b</td><td>c</td></tr>"  # 3 cols -> ignored
        "<tr><th>Grade</th><td>A</td></tr>"  # 2 cols -> kept
        "</table>"
    )
    assert extract_spec_table(html) == [("Grade", "A")]
