"""Structural facts about a schema field's template *section*.

Every parsed schema field carries a ``section`` (e.g. "Product Information",
"Attributes", "Pricing & Inventory", "Shipping", "Media", "Meta"). This module
names the sections that matter to downstream scoring, without reaching into the
locked parser/store/models.

``is_commercial_construct`` flags the "Pricing & Inventory" section: Selling
Unit, Quantity per Selling Unit, prices, discounts. Task 3's real data showed
these are BK selling constructs that a supplier's product page never states, so
counting them as recall gaps unfairly depresses every scraped page's recall.

Deliberately scoped to Pricing & Inventory ONLY for now. Whether other sections
(Shipping / Media / Meta / Identity & Naming) are also structurally
unextractable is an OPEN question — do not assume it here without the data.
"""

from __future__ import annotations

COMMERCIAL_SECTION = "Pricing & Inventory"


def is_commercial_construct(field) -> bool:
    """True iff the field belongs to the Pricing & Inventory section.

    ``field`` is a parsed schema field dict; a non-dict or a field with no
    section is treated as not-commercial (never guesses one on).
    """
    if not isinstance(field, dict):
        return False
    return (field.get("section") or "").strip() == COMMERCIAL_SECTION
