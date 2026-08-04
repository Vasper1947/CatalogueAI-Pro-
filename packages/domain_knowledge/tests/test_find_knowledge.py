"""find_knowledge: family/leaf prefix matching, None for unrelated categories."""

from domain_knowledge.models import CategoryKnowledge, PlausibleRange
from domain_knowledge.store import find_knowledge, write_knowledge


def _tmt():
    return CategoryKnowledge(
        category_path=[
            "Building Materials", "Steel & Reinforcements",
            "High Yield Steel Bars (TMT bars)", "12mm",
        ],
        plausible_ranges={"Diameter": PlausibleRange(6.0, 40.0, "mm", "https://src")},
        standards=[],
        terminology={},
        researched_at="2026-08-04T00:00:00+00:00",
        review_status="confirmed",
    )


def test_family_prefix_finds_leaf_knowledge(tmp_path):
    knowledge = _tmt()
    write_knowledge(knowledge, data_dir=tmp_path)

    # Classified at the 3-level family still finds the 4-level leaf knowledge.
    found = find_knowledge(knowledge.category_path[:3], data_dir=tmp_path)
    assert found is not None
    assert found.plausible_ranges["Diameter"].max == 40.0
    # Exact match also works.
    assert find_knowledge(knowledge.category_path, data_dir=tmp_path) is not None


def test_unrelated_category_finds_nothing(tmp_path):
    write_knowledge(_tmt(), data_dir=tmp_path)
    assert find_knowledge(["Plumbing & Sanitary Ware", "Sanitary Ware"], data_dir=tmp_path) is None
