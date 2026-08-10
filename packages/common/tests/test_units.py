"""Unit-normalization tests: conversions, decimals, dimensions, ambiguity."""

from common.units import convert_from_mm, normalize_value, parse_multi_option_numeric


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


def test_convert_from_mm_to_metres():
    assert convert_from_mm(2500.0, "m") == 2.5


def test_convert_from_mm_to_itself_is_unchanged():
    assert convert_from_mm(12.0, "mm") == 12.0


def test_convert_from_mm_unrecognized_unit_returns_none():
    assert convert_from_mm(2500.0, "furlong") is None


def test_parse_multi_option_numeric_real_supplier_pattern():
    assert parse_multi_option_numeric("2.4/2.5/2.7/3 Meters") == [
        "2.4 Meters", "2.5 Meters", "2.7 Meters", "3.0 Meters",
    ]


def test_parse_multi_option_numeric_drops_trailing_customizable_note():
    assert parse_multi_option_numeric("8/10/12 mm / Customizable") == ["8.0 mm", "10.0 mm", "12.0 mm"]


def test_parse_multi_option_numeric_each_option_reparses_as_confirmed():
    for opt in parse_multi_option_numeric("6/8/10/15/20mm / Customized"):
        value, unit, confidence = normalize_value(opt)
        assert unit is not None and not isinstance(value, list)
        assert confidence >= 0.5


def test_parse_multi_option_numeric_single_value_returns_none():
    assert parse_multi_option_numeric("10 mm") is None


def test_parse_multi_option_numeric_dimension_returns_none():
    assert parse_multi_option_numeric("300 x 600 mm") is None


def test_parse_multi_option_numeric_non_numeric_list_returns_none():
    assert parse_multi_option_numeric("304, 316 Stainless Steel") is None


def test_parse_multi_option_numeric_empty_returns_none():
    assert parse_multi_option_numeric("") is None
    assert parse_multi_option_numeric(None) is None
