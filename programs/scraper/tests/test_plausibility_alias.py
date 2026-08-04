"""Plausibility now flags a Diameter value supplied under an aliased key."""

from domain_knowledge.models import CategoryKnowledge, PlausibleRange
from scraper.assemble import plausibility_checks


def _knowledge():
    return CategoryKnowledge(
        category_path=["Building Materials", "Steel & Reinforcements", "TMT bars", "12mm"],
        plausible_ranges={
            "Diameter": PlausibleRange(6.0, 40.0, "mm", "https://src/diameter")
        },
        standards=[],
        terminology={},
        researched_at="2026-08-04T00:00:00+00:00",
        review_status="confirmed",
    )


def test_diameter_value_under_size_key_flags_plausible():
    checks = plausibility_checks([("Size", "12")], _knowledge())
    assert checks[0]["verdict"] == "plausible"
    assert checks[0]["field"] == "Size"  # the observed key is still reported
    assert checks[0]["source"] == "https://src/diameter"


def test_multi_axis_dimensions_stays_unknown():
    checks = plausibility_checks([("Dimensions", "300 x 600 mm")], _knowledge())
    assert checks[0]["verdict"] == "unknown"
