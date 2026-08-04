"""store round-trip: JSON persistence preserving review_status and every fact."""

from domain_knowledge.models import (
    CategoryKnowledge,
    PlausibleRange,
    Standard,
    TerminologyEntry,
)
from domain_knowledge.store import load_knowledge, write_knowledge


def _knowledge():
    return CategoryKnowledge(
        category_path=[
            "Building Materials", "Steel & Reinforcements",
            "High Yield Steel Bars (TMT bars)", "12mm",
        ],
        plausible_ranges={
            "Diameter": PlausibleRange(6.0, 40.0, "mm", "https://src/diameter"),
        },
        standards=[Standard("IS 1786", "HYSD/TMT reinforcement bars", "https://src/is1786")],
        terminology={
            "TMT": TerminologyEntry("Thermo-Mechanically Treated bar", "https://src/tmt"),
        },
        researched_at="2026-08-04T00:00:00+00:00",
    )


def test_round_trip_preserves_review_status_and_facts(tmp_path):
    original = _knowledge()
    write_knowledge(original, data_dir=tmp_path)
    loaded = load_knowledge(original.category_path, data_dir=tmp_path)

    assert loaded.review_status == "pending_review"
    assert loaded.category_path == original.category_path
    assert loaded.plausible_ranges["Diameter"].max == 40.0
    assert loaded.plausible_ranges["Diameter"].source_url == "https://src/diameter"
    assert loaded.standards[0].name == "IS 1786"
    assert loaded.terminology["TMT"].canonical_term == "Thermo-Mechanically Treated bar"
