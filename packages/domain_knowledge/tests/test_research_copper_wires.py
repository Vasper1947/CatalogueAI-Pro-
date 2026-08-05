"""Electrical & Lighting - Copper Wires research: grounded, sourced, pending_review."""

from domain_knowledge.research import research_category
from domain_knowledge.store import load_knowledge

COPPER_PATH = ["Electrical & Lighting", "Electrical Supplies", "Cables & Wires", "Copper Wires"]

COPPER_SCHEMA = {
    "fields": [
        {"name": "Size"},
        {"name": "Current Carrying Capacity"},
        {"name": "Voltage Rating"},
    ]
}


def test_fresh_copper_wires_knowledge_starts_pending_review():
    findings = {
        "plausible_ranges": [
            {"field": "Size", "min": 0.5, "max": 630, "unit": "sq mm", "source_url": "https://ex/s"},
            {"field": "NotAField", "min": 1, "max": 2, "unit": "A", "source_url": "https://ex/z"},
        ],
        "standards": [{"name": "IS 694", "description": "BIS", "source_url": "https://ex/is694"}],
        "industry_references": [
            {"name": "APAR chart", "description": "mfr", "source_url": "https://ex/apar"}
        ],
        "terminology": [],
    }
    k = research_category(COPPER_PATH, COPPER_SCHEMA, findings)
    assert k.review_status == "pending_review"
    assert set(k.plausible_ranges) == {"Size"}  # NotAField dropped
    assert [s.name for s in k.standards] == ["IS 694"]
    assert [s.name for s in k.industry_references] == ["APAR chart"]


def test_stored_copper_wires_research_is_sourced_and_pending():
    k = load_knowledge(COPPER_PATH)
    assert k.review_status == "pending_review"          # reserved for the user
    assert any("IS 694" in s.name for s in k.standards)  # governing wiring standard
    assert k.industry_references and all(
        s.source_url.startswith("http") for s in k.industry_references
    )
    # grounded to the schema's real numeric fields
    assert "Size" in k.plausible_ranges
    assert "Current Carrying Capacity" in k.plausible_ranges
    assert all(r.source_url.startswith("http") for r in k.plausible_ranges.values())
