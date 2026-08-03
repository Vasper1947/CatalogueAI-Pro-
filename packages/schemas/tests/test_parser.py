"""Parser tests against synthetic fixtures covering the four required cases."""

import zipfile

import pytest
from schemas.parser import TemplateParseError, parse_template, parse_zip


def _parse(path):
    return parse_template(str(path), filename=path.name, zip_category="Zip Cat")


def test_simple_template_fields_types_and_dropdowns(simple_template):
    schema = _parse(simple_template)

    assert schema.category_path == ["Tools"]  # 1-level
    assert schema.category_ids["category_id"] == "cat_tools1"
    assert schema.instructions["row_limit"] == 500
    assert schema.instructions["naming_convention"].startswith("Pattern:")
    assert any("media" in m.lower() for m in schema.instructions["media_options"])

    by = {f.name: f for f in schema.fields}
    assert by["Brand"].type == "dropdown"
    assert by["Brand"].required is True
    assert by["Brand"].dropdown_source == "inline"
    assert by["Brand"].vocabulary == ["Acme", "Globex", "Initech"]
    assert by["Color"].type == "dropdown"
    assert by["Color"].dropdown_source == "lookup:Color"
    assert by["Color"].vocabulary == ["Red", "Green", "Blue"]
    assert by["Weight"].type == "numeric"
    assert by["Model"].type == "string"
    assert schema.lookups["Color"] == ["Red", "Green", "Blue"]


def test_four_level_category_depth(deep_template):
    schema = _parse(deep_template)
    assert len(schema.category_path) == 4
    assert schema.category_path[0] == "Building Materials"
    assert schema.category_path[-1] == "12mm"
    assert set(schema.category_ids) == {
        "category_id", "subcategory_id", "sub_subcategory_id", "product_type_id",
    }
    # header detected on row 2 (section row above); fields still read correctly
    assert {f.name for f in schema.fields} == {"Brand", "Length"}


def test_locked_formula_column_excluded_from_writable(locked_template):
    schema = _parse(locked_template)
    spn = next(f for f in schema.fields if f.name == "System Product Name")
    assert spn.locked is True
    assert spn.is_formula is True
    writable = [f.name for f in schema.writable_fields]
    assert "System Product Name" not in writable
    assert writable == ["Brand", "Price"]


def test_malformed_missing_sheet_raises_clear_error(malformed_template):
    with pytest.raises(TemplateParseError, match="missing required sheet"):
        _parse(malformed_template)


def test_parse_zip_reports_failure_without_dropping_good_files(
    simple_template, malformed_template, tmp_path
):
    zpath = tmp_path / "BK_Mixed.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(simple_template, arcname="Good_-_One.xlsx")
        zf.write(malformed_template, arcname="Bad_-_Two.xlsx")

    schemas, failures = parse_zip(str(zpath))

    assert len(schemas) == 1
    assert len(failures) == 1
    assert "missing required sheet" in failures[0].reason
    assert failures[0].source.endswith("Bad_-_Two.xlsx")
    assert schemas[0].zip_category == "Mixed"
