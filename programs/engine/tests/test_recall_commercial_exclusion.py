"""Recall denominator excludes Pricing & Inventory (commercial-construct) required
fields, but keeps required fields from other sections (e.g. Attributes)."""

from engine.detect import match_template


def _schema(path, fields):
    """fields: list of (name, section, required)."""
    return {
        "category_path": path,
        "fields": [
            {"name": n, "section": s, "required": r, "locked": False, "is_formula": False}
            for n, s, r in fields
        ],
    }


def _ev(*names):
    return [{"field": n, "value": f"v_{n}"} for n in names]


def test_pricing_inventory_required_field_is_not_a_recall_gap():
    schema = _schema(
        ["C"],
        [
            ("Grade", "Product Information", True),   # required, extractable
            ("Material", "Attributes", True),         # required, extractable
            ("Selling Unit", "Pricing & Inventory", True),          # excluded
            ("Quantity per Selling Unit", "Pricing & Inventory", True),  # excluded
        ],
    )
    # Evidence covers only Grade -> the recall denominator is {Grade, Material}.
    _best, _conf, cands = match_template(_ev("Grade"), [schema])
    c = cands[0]
    considered = set(c.required_present) | set(c.required_missing)
    assert considered == {"Grade", "Material"}          # commercial ones dropped
    assert "Selling Unit" not in considered
    assert "Quantity per Selling Unit" not in considered
    assert c.recall == 1 / 2                              # Grade of {Grade, Material}
    assert c.required_missing == ["Material"]


def test_attributes_required_field_still_counts():
    schema = _schema(
        ["C"],
        [("Grade", "Product Information", True), ("Material", "Attributes", True)],
    )
    _best, _conf, cands = match_template(_ev("Grade", "Material"), [schema])
    c = cands[0]
    assert set(c.required_present) == {"Grade", "Material"}
    assert c.recall == 1.0
