"""detect.py: a field-name alias improves the score vs the same evidence without it."""

from engine.detect import match_template


def _schema(path, writable):
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": False, "locked": False, "is_formula": False}
            for n in writable
        ],
    }


def test_alias_raises_detect_score():
    schema = _schema(
        ["Building Materials", "Steel & Reinforcements", "TMT bars", "12mm"],
        ["Diameter", "Brand"],
    )
    # 'Size' aliases to Diameter (schema has Diameter) -> both fields match.
    with_alias = match_template(
        [{"field": "Size", "value": "12"}, {"field": "Brand", "value": "Tata"}], [schema]
    )[1]
    # 'Girth' is not an alias -> only Brand matches.
    without_alias = match_template(
        [{"field": "Girth", "value": "12"}, {"field": "Brand", "value": "Tata"}], [schema]
    )[1]

    assert with_alias == 1.0
    assert without_alias == 0.5
    assert with_alias > without_alias
