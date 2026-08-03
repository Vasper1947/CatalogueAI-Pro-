"""Wiring test: classification_rows emits the tie-resolved suggested_category."""

from scraper.assemble import classification_rows


def _schema(path, naming, breadcrumb):
    return {
        "category_path": path,
        "instructions": {"naming_convention": naming, "breadcrumb": breadcrumb},
    }


def test_suggested_category_row_emitted_when_above_threshold():
    schemas = [
        _schema(
            ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles", "Edge Trim"],
            "Pattern: [Brand] Tile Trim Profile",
            "Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Edge Trim",
        )
    ]
    fields = {"name": "Aluminium Tile Trim", "description": "tile edge profile trim", "sku": "T1"}
    url = "https://example.com/products/t1"

    rows = classification_rows(fields, url, schemas=schemas)

    assert len(rows) == 1
    row = rows[0]
    assert row.field == "suggested_category"
    # single schema -> no tie -> full leaf path
    assert row.value == "Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Edge Trim"
    assert row.source_uri == url
    assert row.method == "scrape"
    assert row.confidence > 0
    assert row.record_id == "T1"  # attached to the same product record


def test_tie_emits_shared_family_prefix_not_a_leaf():
    schemas = [
        _schema(
            ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles", "Corner Profile"],
            "Pattern: [Brand] Tile Trim Profile",
            "Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Corner Profile",
        ),
        _schema(
            ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles", "Transition Profile"],
            "Pattern: [Brand] Tile Trim Profile",
            "Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Transition Profile",
        ),
    ]
    fields = {"name": "Aluminium Tile Trim", "description": "tile edge profile"}
    rows = classification_rows(fields, "https://example.com/p", schemas=schemas)

    assert len(rows) == 1
    assert rows[0].value == "Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles"


def test_no_row_below_threshold():
    schemas = [
        _schema(
            ["Tools & Equipment", "Power Tools", "Drills", "Cordless"],
            "Pattern: [Brand] Cordless Drill",
            "Tools & Equipment > Power Tools > Drills > Cordless",
        )
    ]
    fields = {"name": "Ceramic dinner plate set", "description": "kitchen tableware"}
    assert classification_rows(fields, "https://example.com/p", schemas=schemas) == []


def test_no_row_when_no_name_or_description():
    schemas = [_schema(["A"], "", "")]
    fields = {"sku": "X", "price": "1"}
    assert classification_rows(fields, "https://example.com/p", schemas=schemas) == []
