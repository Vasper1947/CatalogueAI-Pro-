"""Unit-normalization tests: conversions, decimals, dimensions, ambiguity."""

from scraper.units import normalize_value


def test_mm_value_normalizes_confidently():
    value, unit, confidence = normalize_value("9.5 mm")
    assert value == 9.5
    assert unit == "mm"
    assert confidence >= 0.5


def test_inch_converts_to_mm():
    value, unit, _ = normalize_value("1 in")
    assert value == 25.4
    assert unit == "mm"
    value2, unit2, _ = normalize_value('0.5"')
    assert value2 == 12.7
    assert unit2 == "mm"


def test_cm_with_european_comma_decimal():
    value, unit, confidence = normalize_value("1,5 cm")
    assert value == 15.0
    assert unit == "mm"
    assert confidence >= 0.5


def test_dimension_splits_into_components():
    value, unit, confidence = normalize_value("300 x 600 mm")
    assert value == [300.0, 600.0]
    assert unit == "mm"
    assert confidence >= 0.5


def test_number_with_no_unit_is_low_confidence_and_unchanged():
    value, unit, confidence = normalize_value("42")
    assert value == "42"  # original, not a guessed magnitude
    assert unit is None
    assert confidence < 0.5


def test_ambiguous_separator_is_low_confidence():
    value, _unit, confidence = normalize_value("1,234")  # thousands vs decimal
    assert value == "1,234"  # unchanged, not a guessed 1234 or 1.234
    assert confidence < 0.5


def test_categorical_string_passes_through():
    value, unit, confidence = normalize_value("Aluminium")
    assert value == "Aluminium"
    assert unit is None
    assert confidence >= 0.5
