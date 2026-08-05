"""Field-name aliases: map observed field names onto canonical schema fields.

These are judgment calls, not sourced facts, so every entry states its reasoning
for spot-checking. Scope is deliberately narrow — TMT-relevant fields (Diameter,
Grade, Length), a small genuinely-universal set (Brand, Color), and Edge Trims
fields (Size, Length) — mirroring domain_knowledge's one-category-at-a-time
discipline.

Some aliases are value-conditional via an ``applies_when`` guard evaluated
against the field's value. In particular "Dimensions"/"Height" resolve ONLY when
the value is a single-axis length — one value, or a same-axis option list like
"8/10/12mm" (how supplier pages often state a trim's size), with an mm/cm/inch
unit and no "x"/"×" separator. A multi-axis "300 x 600 mm" is a footprint, not a
single dimension, and is NOT aliased.

Aliases are also category-aware: ``resolve_field`` only rewrites an observed name
to a canonical field that the target schema/category actually has (via
``available_fields``). This is why "Size" -> Diameter for a TMT bar (whose schema
has Diameter) but stays "Size" for an Edge Trim (whose own schema field IS
"Size").
"""

from __future__ import annotations

import re

FIELD_ALIASES: dict[str, list[dict]] = {
    # --- TMT / reinforcement bars ---
    "Diameter": [
        {"alias": "Size", "applies_when": None,
         "reasoning": "For round-profile items (bars, rods, round trims) the single "
                      "'Size' figure is the nominal diameter."},
        {"alias": "Dimensions", "applies_when": "single_axis_length",
         "reasoning": "'Dimensions' is a diameter ONLY when it is a single-axis length "
                      "(one value, or same-axis options like '12/16mm'; a number + "
                      "mm/cm/inch, no x/×). A multi-axis '300 x 600 mm' is a footprint."},
        {"alias": "Dia", "applies_when": None,
         "reasoning": "Common trade abbreviation of Diameter."},
    ],
    "Grade": [
        {"alias": "Steel Grade", "applies_when": None,
         "reasoning": "For steel/rebar, 'Steel Grade' names the same Grade field."},
        {"alias": "Fe Grade", "applies_when": None,
         "reasoning": "'Fe Grade' is the IS 1786 grade designation (Fe415/500/…)."},
    ],
    "Length": [
        {"alias": "Cut Length", "applies_when": None,
         "reasoning": "The cut/stock length of a bar or profile is its Length."},
        {"alias": "Bar Length", "applies_when": None,
         "reasoning": "'Bar Length' is the Length field for rebar."},
        {"alias": "Overall Length", "applies_when": None,
         "reasoning": "'Overall Length' is the total Length of a profile/trim."},
        {"alias": "Roll Length", "applies_when": None,
         "reasoning": "For rolled goods the roll length is the Length."},
    ],
    # --- Genuinely universal ---
    "Brand": [
        {"alias": "Manufacturer", "applies_when": None,
         "reasoning": "Universal: the manufacturer is the brand for cataloguing."},
    ],
    "Color": [
        {"alias": "Colour", "applies_when": None,
         "reasoning": "Universal UK/US spelling variant; BK schemas use 'Color'."},
    ],
    # --- Edge Trims & Profiles (the schema's own fields are 'Size' and 'Length') ---
    "Size": [
        {"alias": "Height", "applies_when": "single_axis_length",
         "reasoning": "A tile trim's 'Size' is its height (the tile thickness it "
                      "caps). Real pages state this as one measure or a same-axis "
                      "option list ('8/10/12mm'); only a multi-axis value is not a Size."},
        {"alias": "Profile Height", "applies_when": "single_axis_length",
         "reasoning": "'Profile Height' is the trim's Size (a single-axis length)."},
        {"alias": "Tile Thickness", "applies_when": "single_axis_length",
         "reasoning": "A trim is chosen by the tile thickness it caps, which is its "
                      "Size (a single-axis length)."},
    ],
}

_LENGTH_UNIT = r"(?:mm|cm|millimet(?:er|re)s?|centimet(?:er|re)s?|in|inch(?:es)?|[\"″])"


def _is_single_axis_length(value: object) -> bool:
    """True if value is a length along ONE axis: at least one number with an
    mm/cm/inch unit and no x/× axis separator. Accepts a same-axis option list
    like '8/10/12mm' (real supplier pages state a trim's size that way — e.g. TBK
    Metal Edge Trim 'Height: 8/10/12mm'); rejects a multi-axis '300 x 600 mm'."""
    if value is None:
        return False
    text = str(value)
    if "x" in text.lower() or "×" in text:
        return False
    if not re.search(r"(?i)" + _LENGTH_UNIT, text):
        return False
    return len(re.findall(r"[0-9][0-9.,]*", text)) >= 1


_GUARDS = {"single_axis_length": _is_single_axis_length}


def _normalize(name: object) -> str:
    return re.sub(r"[\s_\-]+", " ", str(name).strip().lower())


# Reverse index: normalized alias -> [(canonical_field, applies_when), ...].
_ALIAS_INDEX: dict[str, list[tuple[str, str | None]]] = {}
for _canonical_field, _entries in FIELD_ALIASES.items():
    for _entry in _entries:
        _ALIAS_INDEX.setdefault(_normalize(_entry["alias"]), []).append(
            (_canonical_field, _entry["applies_when"])
        )


def resolve_field(name, value=None, available_fields=None) -> str:
    """Resolve an observed field name to a canonical schema field, or return it.

    Rewrites only when ``name`` is a known alias whose ``applies_when`` guard (if
    any) is satisfied by ``value`` AND — when ``available_fields`` is given —
    whose canonical target is actually a field of the target schema/category.
    So 'Size' -> Diameter for a schema that has Diameter, but stays 'Size' for a
    schema whose own field is 'Size'. Unknown names are returned unchanged.
    """
    candidates = [
        (canonical_field, applies_when)
        for canonical_field, applies_when in _ALIAS_INDEX.get(_normalize(name), [])
        if applies_when is None or _GUARDS[applies_when](value)
    ]
    if not candidates:
        return name
    if available_fields is not None:
        present = [cf for cf, _ in candidates if cf in available_fields]
        return present[0] if present else name
    return candidates[0][0]
