"""Deterministic plausibility flagging against researched domain knowledge.

``check_plausibility`` only FLAGS a value — it never modifies or rejects one,
makes no network call, and involves no Claude call. A field with no researched
range returns "unknown"; it never guesses a verdict in either direction.
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _extract_number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def _range_bounds(entry: object) -> tuple[float | None, float | None]:
    if isinstance(entry, dict):
        return entry.get("min"), entry.get("max")
    return getattr(entry, "min", None), getattr(entry, "max", None)


def check_plausibility(field_name: str, value: object, category_knowledge: object) -> str:
    """Return 'plausible' | 'implausible' | 'unknown'. Flags only, never mutates."""
    if isinstance(category_knowledge, dict):
        ranges = category_knowledge.get("plausible_ranges")
    else:
        ranges = getattr(category_knowledge, "plausible_ranges", None)
    if not ranges:
        return "unknown"

    entry = ranges.get(field_name)
    if entry is None:
        return "unknown"

    low, high = _range_bounds(entry)
    number = _extract_number(value)
    if number is None or low is None or high is None:
        return "unknown"
    return "plausible" if low <= number <= high else "implausible"
