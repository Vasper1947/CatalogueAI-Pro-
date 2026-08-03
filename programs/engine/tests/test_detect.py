"""Detection tests (synthetic schemas, no disk)."""

from engine.detect import MATCH_THRESHOLD, match_template


def _ev(*names):
    return [{"field": n, "value": f"v_{n}", "absence": False} for n in names]


def _schema(path, writable):
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": False, "locked": False, "is_formula": False}
            for n in writable
        ],
    }


def test_close_match_scores_high_and_maps_fields():
    schemas = [
        _schema(["Tools", "Drills"], ["Brand", "Model", "Voltage", "Weight"]),
        _schema(["Plumbing", "Basins"], ["Brand", "Colour", "Shape"]),
    ]
    best, confidence, candidates = match_template(_ev("Brand", "Model", "Voltage"), schemas)

    assert best is not None
    assert best["category_path"] == ["Tools", "Drills"]
    assert confidence == 1.0  # all 3 evidence fields map
    assert candidates[0].category_path == ["Tools", "Drills"]
    assert set(candidates[0].matched_fields) == {"Brand", "Model", "Voltage"}


def test_unrelated_fields_below_threshold_return_none():
    schemas = [_schema(["Tools", "Drills"], ["Brand", "Model", "Voltage", "Weight"])]
    best, confidence, candidates = match_template(_ev("sku_xyz", "random_attr", "foo"), schemas)

    assert best is None  # not a forced guess
    assert confidence < MATCH_THRESHOLD
    assert candidates  # what was close is still reported


def test_synonyms_title_name_and_cost_price():
    schemas = [_schema(["Cat"], ["Name", "Price", "Brand"])]
    best, confidence, _ = match_template(_ev("title", "cost", "brand"), schemas)

    assert best is not None
    assert confidence == 1.0  # title->name, cost->price, brand->brand
