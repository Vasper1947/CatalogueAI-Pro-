"""Value normalization for spec values — shared, non-domain-specific utility.

Lives in ``packages/common`` (with errors/logging) because both programs depend
on it: the scraper (spec-table extraction) and the engine (sibling-size
comparison in template detection) import the same ``normalize_value``.

    normalize_value(raw) -> (normalized_value, unit, confidence)

Canonical length unit is millimetres. Handles mm/cm/m/inch conversion, European
vs US decimal/thousands separators, and simple "A x B [x C]" dimension strings.
Genuinely ambiguous input — a number with no stated unit, or conflicting
separators — is returned unchanged with LOW confidence; it is never guessed into
a number. Non-numeric categorical values (e.g. a material name) pass through as
they are, at normal confidence.
"""

from __future__ import annotations

import re

CANONICAL_UNIT = "mm"
HIGH = 0.9
LOW = 0.3

# Recognised unit tokens -> factor to millimetres.
_TO_MM: dict[str, float] = {
    "mm": 1.0, "millimeter": 1.0, "millimetre": 1.0,
    "millimeters": 1.0, "millimetres": 1.0,
    "cm": 10.0, "centimeter": 10.0, "centimetre": 10.0,
    "centimeters": 10.0, "centimetres": 10.0,
    "m": 1000.0, "meter": 1000.0, "metre": 1000.0,
    "meters": 1000.0, "metres": 1000.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4, '"': 25.4, "″": 25.4,
}

# Longest alternatives first so e.g. "mm" wins over "m", "inches" over "in".
_UNIT_PATTERN = (
    r"(?:millimet(?:er|re)s?|centimet(?:er|re)s?|met(?:er|re)s?"
    r"|inches|inch|mm|cm|in|m|\"|″)"
)
_COMPONENT = r"[0-9][0-9.,]*"

_DIM_RE = re.compile(
    r"(?i)^\s*(" + _COMPONENT + r")\s*[x×]\s*(" + _COMPONENT + r")"
    r"(?:\s*[x×]\s*(" + _COMPONENT + r"))?\s*(" + _UNIT_PATTERN + r")?\s*$"
)
_SINGLE_RE = re.compile(r"(?i)^\s*([+-]?" + _COMPONENT + r")\s*(" + _UNIT_PATTERN + r")?\s*$")


def _unit_to_mm(token: str | None) -> float | None:
    if token is None:
        return None
    return _TO_MM.get(token.strip().lower())


def _parse_number(num_str: str) -> tuple[float | None, bool]:
    """Parse a numeric string. Returns (value | None, ambiguous)."""
    s = num_str.replace(" ", "").strip()
    if not s:
        return None, False
    has_dot = "." in s
    has_comma = "," in s
    try:
        if has_dot and has_comma:
            # The last-occurring separator is the decimal point.
            if s.rfind(".") > s.rfind(","):
                return float(s.replace(",", "")), False
            return float(s.replace(".", "").replace(",", ".")), False
        if has_comma:
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                return float(s.replace(",", ".")), False  # European decimal
            if len(parts) == 2 and len(parts[1]) == 3:
                return float(s.replace(",", "")), True  # 1,234 -> thousands vs decimal: ambiguous
            return float(s.replace(",", "")), False  # grouped thousands
        if has_dot and s.count(".") > 1:
            return float(s.replace(".", "")), False  # 1.234.567 -> grouped thousands
        return float(s), False
    except ValueError:
        return None, False


def _fmt(n: float) -> float:
    return round(n, 4)


def normalize_value(raw_value) -> tuple[object, str | None, float]:
    """Normalize one spec value to (normalized_value, unit, confidence)."""
    raw = str(raw_value).strip()
    if not raw:
        return raw, None, LOW

    dim = _DIM_RE.match(raw)
    if dim and dim.group(2):
        factor = _unit_to_mm(dim.group(4))
        components = [g for g in (dim.group(1), dim.group(2), dim.group(3)) if g]
        numbers: list[float] = []
        ok = factor is not None
        for comp in components:
            value, ambiguous = _parse_number(comp)
            if value is None or ambiguous:
                ok = False
                break
            numbers.append(value)
        if ok and len(numbers) >= 2:
            return [_fmt(n * factor) for n in numbers], CANONICAL_UNIT, HIGH
        return raw, None, LOW  # a dimension we cannot resolve without guessing

    single = _SINGLE_RE.match(raw)
    if single and any(ch.isdigit() for ch in single.group(1)):
        value, ambiguous = _parse_number(single.group(1))
        factor = _unit_to_mm(single.group(2))
        if value is None or ambiguous:
            return raw, None, LOW  # conflicting separators / unparseable
        if factor is not None:
            return _fmt(value * factor), CANONICAL_UNIT, HIGH
        return raw, None, LOW  # a number with no unit stated -> don't assume one

    # Non-numeric categorical value: nothing to normalize, and not ambiguous.
    return raw, None, HIGH


def convert_from_mm(value_mm: float, target_unit: str) -> float | None:
    """Convert a canonical-mm value into target_unit. Returns None for an
    unrecognized unit — never guesses a conversion factor. Used by
    engine/writer.py so a numeric field is written in ITS OWN schema unit
    (e.g. metres for Length), not blindly in normalize_value's canonical mm —
    writing 2500 into a field whose real unit is "m" would be a fabricated-
    looking value, not a faithful one.
    """
    factor = _unit_to_mm(target_unit)
    if factor is None:
        return None
    return _fmt(value_mm / factor)
