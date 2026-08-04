"""standards vs industry_references: routing, round-trip, and migrated data.

A genuine governing standard (IS 1786) stays under ``standards``; a real but
manufacturer-only spec (Schluter profiles) belongs under ``industry_references``.
"""

from domain_knowledge.models import CategoryKnowledge, Standard
from domain_knowledge.research import research_category
from domain_knowledge.store import load_knowledge, write_knowledge

TMT_PATH = [
    "Building Materials",
    "Steel & Reinforcements",
    "High Yield Steel Bars (TMT bars)",
    "12mm",
]
EDGE_PATH = ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles"]


def test_research_routes_standards_and_industry_references_separately():
    findings = {
        "plausible_ranges": [],
        "standards": [
            {"name": "IS 9999", "description": "gov std", "source_url": "https://gov/s"}
        ],
        "industry_references": [
            {"name": "Acme datasheet", "description": "mfr", "source_url": "https://acme/d"}
        ],
        "terminology": [],
    }
    k = research_category(["A", "B"], {"fields": [{"name": "Size"}]}, findings)
    assert [s.name for s in k.standards] == ["IS 9999"]
    assert [s.name for s in k.industry_references] == ["Acme datasheet"]
    assert k.review_status == "pending_review"


def test_industry_references_roundtrip_to_from_dict():
    k = CategoryKnowledge(
        category_path=["A"],
        plausible_ranges={},
        standards=[Standard("S", "d", "https://s")],
        terminology={},
        researched_at="t",
        industry_references=[Standard("R", "d", "https://r")],
    )
    d = k.to_dict()
    assert d["industry_references"][0]["name"] == "R"
    k2 = CategoryKnowledge.from_dict(d)
    assert [s.name for s in k2.industry_references] == ["R"]
    assert [s.name for s in k2.standards] == ["S"]


def test_pre_split_data_without_industry_references_still_loads():
    # A stored file written before the split has no industry_references key.
    legacy = {
        "category_path": ["A"],
        "plausible_ranges": {},
        "standards": [{"name": "IS 1", "description": "", "source_url": "https://x"}],
        "terminology": {},
        "researched_at": "t",
        "review_status": "confirmed",
    }
    k = CategoryKnowledge.from_dict(legacy)
    assert k.industry_references == []


def test_store_roundtrips_industry_references(tmp_path):
    k = CategoryKnowledge(
        category_path=["A", "B"],
        plausible_ranges={},
        standards=[],
        terminology={},
        researched_at="t",
        industry_references=[Standard("R", "d", "https://r")],
    )
    write_knowledge(k, tmp_path)
    loaded = load_knowledge(["A", "B"], tmp_path)
    assert [s.name for s in loaded.industry_references] == ["R"]


def test_tmt_migrated_data_keeps_is1786_under_standards():
    k = load_knowledge(TMT_PATH)
    assert k.standards, "TMT must keep its regulatory standards"
    assert all("IS 1786" in s.name for s in k.standards)
    assert k.industry_references == []  # nothing wrongly moved


def test_edge_trims_migrated_data_moved_to_industry_references():
    k = load_knowledge(EDGE_PATH)
    assert k.standards == []  # no manufacturer spec left masquerading as a standard
    names = [s.name for s in k.industry_references]
    assert len(names) == 2 and all("Schluter" in n for n in names)
    assert k.review_status == "pending_review"  # still not confirmed
