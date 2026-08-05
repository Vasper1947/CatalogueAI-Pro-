"""Alias resolution: category-aware, value-guarded field-name aliasing."""

from schemas.aliases import resolve_field


def test_size_resolves_to_diameter_for_a_round_item_category():
    assert resolve_field("Size", "12", available_fields={"Diameter"}) == "Diameter"
    # No category context -> the primary target (Diameter).
    assert resolve_field("Size", "12") == "Diameter"


def test_size_stays_size_when_the_schema_field_is_size():
    # An Edge Trim schema's own field is 'Size' -> it is not aliased away.
    assert resolve_field("Size", "12", available_fields={"Size", "Length"}) == "Size"


def test_lone_length_dimensions_resolves_to_diameter():
    assert resolve_field("Dimensions", "12 mm", available_fields={"Diameter"}) == "Diameter"
    assert resolve_field(
        "Dimensions", "12 Millimeter (mm)", available_fields={"Diameter"}
    ) == "Diameter"


def test_multi_axis_dimensions_does_not_resolve():
    assert resolve_field("Dimensions", "300 x 600 mm", available_fields={"Diameter"}) == "Dimensions"


def test_unitless_dimensions_does_not_resolve():
    assert resolve_field("Dimensions", "12", available_fields={"Diameter"}) == "Dimensions"


def test_universal_manufacturer_and_colour():
    assert resolve_field("Manufacturer", "Tata", available_fields={"Brand"}) == "Brand"
    assert resolve_field("Colour", "Silver", available_fields={"Color"}) == "Color"


def test_edge_trims_height_resolves_to_size_for_single_axis_length():
    assert resolve_field("Height", "10mm", available_fields={"Size", "Length"}) == "Size"
    # A same-axis option list (real supplier pages state size this way, e.g. TBK
    # Metal Edge Trim 'Height: 8/10/12mm') is one axis -> resolves to Size.
    assert resolve_field("Height", "8/10/12mm", available_fields={"Size", "Length"}) == "Size"
    # A multi-axis value is NOT a Size.
    assert resolve_field("Height", "8 x 10 mm", available_fields={"Size", "Length"}) == "Height"


def test_edge_trims_overall_length_resolves_to_length():
    assert resolve_field("Overall Length", "2.5 m", available_fields={"Size", "Length"}) == "Length"


def test_unknown_field_is_unchanged():
    assert resolve_field("Payment Terms", "L/C", available_fields={"Diameter"}) == "Payment Terms"
