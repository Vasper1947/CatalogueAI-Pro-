"""GI (galvanized iron) pipe research: a second Plumbing sub-category with
genuinely different standards than PVC. Grounded, sourced, pending_review.
"""

from domain_knowledge.research import research_category
from domain_knowledge.store import load_knowledge

GI_PATH = ["Plumbing & Sanitary Ware", "Plumbing Materials", "Pipes & Fittings", "GI"]

GI_SCHEMA = {
    "fields": [{"name": "Nominal Diameter"}, {"name": "Wall Thickness"}, {"name": "Material"}]
}


def test_fresh_gi_knowledge_starts_pending_review():
    findings = {
        "plausible_ranges": [
            {"field": "Nominal Diameter", "min": 15, "max": 150, "unit": "mm", "source_url": "https://ex/d"},
            {"field": "NotAField", "min": 1, "max": 2, "unit": "mm", "source_url": "https://ex/z"},
        ],
        "standards": [{"name": "IS 1239", "description": "BIS", "source_url": "https://ex/is1239"}],
        "industry_references": [
            {"name": "Sachiya chart", "description": "mfr", "source_url": "https://ex/sachiya"}
        ],
        "terminology": [],
    }
    k = research_category(GI_PATH, GI_SCHEMA, findings)
    assert k.review_status == "pending_review"
    assert set(k.plausible_ranges) == {"Nominal Diameter"}  # NotAField dropped
    assert [s.name for s in k.standards] == ["IS 1239"]
    assert [s.name for s in k.industry_references] == ["Sachiya chart"]


def test_stored_gi_research_is_sourced_and_pending_with_different_standards_than_pvc():
    gi = load_knowledge(GI_PATH)
    assert gi.review_status == "pending_review"
    assert any("IS 1239" in s.name for s in gi.standards)   # metal-pipe standard
    # genuinely different from PVC's governing standard
    pvc = load_knowledge(["Plumbing & Sanitary Ware", "Plumbing Materials", "Pipes & Fittings", "PVC"])
    gi_std = {s.name for s in gi.standards}
    pvc_std = {s.name for s in pvc.standards}
    assert not (gi_std & pvc_std)                            # no shared standard
    assert gi.industry_references and all(
        s.source_url.startswith("http") for s in gi.industry_references
    )
    assert all(r.source_url.startswith("http") for r in gi.plausible_ranges.values())
