"""Edge Trims research starts pending_review and grounds to its real fields."""

from domain_knowledge.research import research_category

EDGE_SCHEMA = {
    "fields": [{"name": "Size"}, {"name": "Length"}, {"name": "Material"}, {"name": "Brand"}]
}

EDGE_FINDINGS = {
    "plausible_ranges": [
        {"field": "Size", "min": 4, "max": 30, "unit": "mm", "source_url": "https://ex/size"},
        {"field": "Length", "min": 2.0, "max": 3.3, "unit": "m", "source_url": "https://ex/len"},
        {"field": "NotAField", "min": 1, "max": 2, "unit": "x", "source_url": "https://ex/z"},
    ],
    "standards": [],
    "terminology": [],
}


def test_edge_trims_research_starts_pending_review():
    knowledge = research_category(
        ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles"],
        EDGE_SCHEMA,
        EDGE_FINDINGS,
    )
    assert knowledge.review_status == "pending_review"
    # grounded to real schema fields only (NotAField dropped)
    assert set(knowledge.plausible_ranges) == {"Size", "Length"}
