"""Vessel Basins research: starts pending_review, grounds to its real fields,
and routes a governing standard vs a manufacturer spec correctly.
"""

from domain_knowledge.research import research_category
from domain_knowledge.store import load_knowledge

VESSEL_PATH = [
    "Plumbing & Sanitary Ware",
    "Sanitary Ware",
    "Wash Basins & Pedestals",
    "Vessel Basins",
]

# Minimal stand-in for the real Vessel Basins schema fields we range on.
VESSEL_SCHEMA = {
    "fields": [
        {"name": "Drain Size"},
        {"name": "Dimensions (1)"},
        {"name": "Material"},
    ]
}


def test_fresh_sanitary_ware_knowledge_starts_pending_review():
    findings = {
        "plausible_ranges": [
            {"field": "Drain Size", "min": 32, "max": 40, "unit": "mm", "source_url": "https://ex/d"},
            {"field": "NotAField", "min": 1, "max": 2, "unit": "mm", "source_url": "https://ex/z"},
        ],
        "standards": [
            {"name": "IS 2556", "description": "BIS", "source_url": "https://ex/is2556"}
        ],
        "industry_references": [
            {"name": "Karran spec", "description": "mfr", "source_url": "https://ex/karran"}
        ],
        "terminology": [],
    }
    k = research_category(VESSEL_PATH, VESSEL_SCHEMA, findings)
    assert k.review_status == "pending_review"  # never confirmed on research
    # grounded to real schema fields only (NotAField dropped)
    assert set(k.plausible_ranges) == {"Drain Size"}
    # regulatory vs manufacturer routed to the right bucket
    assert [s.name for s in k.standards] == ["IS 2556"]
    assert [s.name for s in k.industry_references] == ["Karran spec"]


def test_stored_vessel_basins_research_is_sourced_and_pending():
    k = load_knowledge(VESSEL_PATH)
    assert k.review_status == "pending_review"
    # regulatory standard under standards; manufacturer specs under references
    assert any("IS 2556" in s.name for s in k.standards)
    assert k.industry_references and all(
        s.source_url.startswith("http") for s in k.industry_references
    )
    # every range carries a source
    assert k.plausible_ranges and all(
        r.source_url.startswith("http") for r in k.plausible_ranges.values()
    )
    assert "Drain Size" in k.plausible_ranges
