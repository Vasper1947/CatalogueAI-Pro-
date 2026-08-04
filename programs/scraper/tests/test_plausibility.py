"""Plausibility wiring: flags a parallel structure, never edits evidence values."""

from domain_knowledge.models import CategoryKnowledge, PlausibleRange
from scraper.assemble import plausibility_checks, to_evidence_rows


def _confirmed_knowledge():
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


def test_in_range_value_flags_plausible_with_source():
    checks = plausibility_checks([("Diameter", "12")], _confirmed_knowledge())
    assert checks == [
        {
            "field": "Diameter",
            "value": "12",
            "verdict": "plausible",
            "source": "https://src/diameter",
        }
    ]


def test_out_of_range_flags_implausible_but_evidence_value_untouched():
    fields = {"Diameter": "999"}
    rows = to_evidence_rows(fields, "https://ex.com/p")
    checks = plausibility_checks([("Diameter", "999")], _confirmed_knowledge())

    assert checks[0]["verdict"] == "implausible"
    # Flagging never edits or drops data: the EvidenceRow's value is unchanged.
    assert [r.value for r in rows if r.field == "Diameter"] == ["999"]


def test_no_knowledge_every_field_unknown_and_no_error():
    checks = plausibility_checks([("Diameter", "12"), ("Brand", "Tata")], None)
    assert [c["verdict"] for c in checks] == ["unknown", "unknown"]
    assert all(c["source"] is None for c in checks)
