"""Store tests: schema -> JSON on disk + index, and load it back."""

from schemas.parser import parse_template
from schemas.store import load_index, load_schema, write_all


def test_write_all_and_load_roundtrip(simple_template, tmp_path):
    schema = parse_template(
        str(simple_template), filename=simple_template.name, zip_category="Tools Cat"
    )
    data_dir = tmp_path / "data"

    write_all([schema], data_dir=data_dir)

    index = load_index(data_dir)
    key = " > ".join(schema.category_path)
    assert key in index
    assert index[key]["product_type_id"] == schema.category_ids.get("product_type_id")

    loaded = load_schema(schema.category_path, data_dir=data_dir)
    assert loaded["category_ids"]["category_id"] == "cat_tools1"
    assert "Brand" in [f["name"] for f in loaded["fields"]]
    assert loaded["writable_fields"]  # serialized convenience list present
