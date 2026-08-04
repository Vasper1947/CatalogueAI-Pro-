"""PVC pipe research: starts pending_review, grounds to its real numeric fields,
and routes governing standards vs manufacturer specs correctly.
"""

from domain_knowledge.research import research_category
from domain_knowledge.store import load_knowledge

PVC_PATH = ["Plumbing & Sanitary Ware", "Plumbing Materials", "Pipes & Fittings", "PVC"]

PVC_SCHEMA = {
    "fields": [
        {"name": "Nominal Diameter"},
        {"name": "Wall Thickness"},
        {"name": "Pressure Class"},
    ]
}


def test_fresh_plumbing_knowledge_starts_pending_review():
    findings = {
        "plausible_ranges": [
            {"field": "Nominal Diameter", "min": 25, "max": 630, "unit": "mm", "source_url": "https://ex/d"},
            {"field": "NotAField", "min": 1, "max": 2, "unit": "mm", "source_url": "https://ex/z"},
        ],
        "standards": [
            {"name": "IS 4985", "description": "BIS", "source_url": "https://ex/is4985"}
        ],
        "industry_references": [
            {"name": "Wavin catalogue", "description": "mfr", "source_url": "https://ex/wavin"}
        ],
        "terminology": [],
    }
    k = research_category(PVC_PATH, PVC_SCHEMA, findings)
    assert k.review_status == "pending_review"  # never confirmed on research
    assert set(k.plausible_ranges) == {"Nominal Diameter"}  # NotAField dropped
    assert [s.name for s in k.standards] == ["IS 4985"]
    assert [s.name for s in k.industry_references] == ["Wavin catalogue"]


def test_stored_pvc_research_is_sourced_and_pending():
    k = load_knowledge(PVC_PATH)
    assert k.review_status == "pending_review"  # reserved for the user to confirm
    assert any("IS 4985" in s.name for s in k.standards)          # governing standard
    assert k.industry_references and all(                          # manufacturer specs
        s.source_url.startswith("http") for s in k.industry_references
    )
    assert "Nominal Diameter" in k.plausible_ranges
    assert all(r.source_url.startswith("http") for r in k.plausible_ranges.values())
