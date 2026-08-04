"""Brand vocabulary matching: whole-word, case-insensitive, sourced, no fuzzy."""

from scraper.assemble import CONFIDENCE_VOCABULARY, match_brand_from_vocabulary


def _schema_with_brands(brands):
    return {"category_path": ["C"], "lookups": {"Brand": brands}, "fields": []}


def test_matches_whole_word_brand_in_text_and_sources_it():
    schema = _schema_with_brands(["TATA", "Bosch", "L&T"])
    row = match_brand_from_vocabulary(
        "12mm TATA TMT bar for construction",
        schema,
        source_uri="https://x/p",
        record_id="P1",
    )
    assert row is not None
    assert row.field == "Brand"
    assert row.value == "TATA"
    assert row.source_uri == "https://x/p"
    assert row.confidence == CONFIDENCE_VOCABULARY
    assert row.confidence < 0.9  # below JSON-LD / spec-table tiers


def test_no_vocabulary_brand_in_text_emits_nothing():
    schema = _schema_with_brands(["Bosch", "Makita"])
    assert (
        match_brand_from_vocabulary(
            "12mm SP Steel TMT bar", schema, source_uri="https://x", record_id="P1"
        )
        is None
    )


def test_schema_without_brand_vocabulary_emits_nothing():
    # The TMT case: Brand is a free-text field, no lookup vocabulary.
    schema = {"category_path": ["C"], "lookups": {}, "fields": []}
    assert (
        match_brand_from_vocabulary(
            "TATA anything", schema, source_uri="https://x", record_id="P1"
        )
        is None
    )


def test_whole_word_not_substring():
    schema = _schema_with_brands(["India"])
    # Substring inside 'Indiana' must NOT match.
    assert (
        match_brand_from_vocabulary(
            "Indiana Steel Works", schema, source_uri="https://x", record_id="P1"
        )
        is None
    )
    # Standalone whole word does match (documents the generic-vocab caveat).
    assert (
        match_brand_from_vocabulary(
            "Made in India", schema, source_uri="https://x", record_id="P1"
        )
        is not None
    )


def test_multi_word_brand_matches_whole_phrase():
    schema = _schema_with_brands(["Golden Diamond"])
    row = match_brand_from_vocabulary(
        "Golden Diamond premium tiles", schema, source_uri="https://x", record_id="P1"
    )
    assert row is not None and row.value == "Golden Diamond"
