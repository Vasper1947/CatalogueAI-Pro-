"""check_plausibility: range flagging, unknown for un-ranged fields, no guessing."""

from domain_knowledge.models import CategoryKnowledge, PlausibleRange


def _knowledge():
    return CategoryKnowledge(
        category_path=["Building Materials", "Steel & Reinforcements", "TMT bars", "12mm"],
        plausible_ranges={
            "Diameter": PlausibleRange(min=6.0, max=40.0, unit="mm", source_url="https://x")
        },
        standards=[],
        terminology={},
        researched_at="2026-08-04T00:00:00+00:00",
    )


def test_value_inside_range_is_plausible():
    from domain_knowledge.check import check_plausibility

    assert check_plausibility("Diameter", "12", _knowledge()) == "plausible"
    assert check_plausibility("Diameter", "12mm", _knowledge()) == "plausible"


def test_value_outside_range_is_implausible():
    from domain_knowledge.check import check_plausibility

    assert check_plausibility("Diameter", "500", _knowledge()) == "implausible"


def test_field_without_a_researched_range_is_unknown():
    from domain_knowledge.check import check_plausibility

    assert check_plausibility("Brand", "Tata", _knowledge()) == "unknown"


def test_unparseable_value_is_unknown_not_guessed():
    from domain_knowledge.check import check_plausibility

    assert check_plausibility("Diameter", "n/a", _knowledge()) == "unknown"
