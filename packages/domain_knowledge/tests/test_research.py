"""research_category: grounds to schema fields, requires sources, starts pending."""

from domain_knowledge.research import research_category

SCHEMA = {
    "fields": [
        {"name": "Diameter"},
        {"name": "Length"},
        {"name": "Grade"},
        {"name": "Brand"},
    ]
}

FINDINGS = {
    "plausible_ranges": [
        {"field": "Diameter", "min": 6, "max": 40, "unit": "mm", "source_url": "https://is1786"},
        {"field": "Length", "min": 6, "max": 12, "unit": "m", "source_url": "https://len"},
        {"field": "NotAField", "min": 1, "max": 2, "unit": "x", "source_url": "https://z"},
        {"field": "Grade", "min": 415, "max": 600, "unit": "MPa"},  # no source_url
    ],
    "standards": [
        {"name": "IS 1786", "description": "HYSD bars", "source_url": "https://is1786"},
        {"name": "Unsourced Standard", "description": "..."},  # no source_url
    ],
    "terminology": [
        {"synonym": "TMT", "canonical_term": "Thermo-Mechanically Treated bar", "source_url": "https://t"},
        {"synonym": "rebar", "canonical_term": "reinforcement bar"},  # no source_url
    ],
}


def test_freshly_researched_starts_pending_review():
    knowledge = research_category(["Building Materials", "TMT", "12mm"], SCHEMA, FINDINGS)
    assert knowledge.review_status == "pending_review"


def test_ranges_are_grounded_to_real_schema_fields_only():
    knowledge = research_category(["x"], SCHEMA, FINDINGS)
    # NotAField dropped (not in schema); Grade dropped (no source_url)
    assert set(knowledge.plausible_ranges) == {"Diameter", "Length"}
    assert knowledge.plausible_ranges["Diameter"].source_url == "https://is1786"


def test_unsourced_facts_are_dropped():
    knowledge = research_category(["x"], SCHEMA, FINDINGS)
    assert [s.name for s in knowledge.standards] == ["IS 1786"]
    assert set(knowledge.terminology) == {"TMT"}
