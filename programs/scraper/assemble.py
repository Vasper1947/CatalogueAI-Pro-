"""Assemble discovered fields into a BK-PACK using packages/bkpack as-is.

Each field that structured data actually provided becomes one EvidenceRow whose
source_uri is the exact page URL it was read from. A field the page did not
provide simply has no row — it is never filled with a guess. The rows are handed
to build_bkpack() from packages/bkpack, which is used exactly as it already
exists (no changes to that package).
"""

from __future__ import annotations

from urllib.parse import urlparse

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from schemas.classify import (
    CLASSIFY_THRESHOLD,
    classify_category,
    load_schemas,
    top_suggestion,
)

# Confidence reflects provenance: schema.org JSON-LD is high-trust structured
# data; a looser (non-structured) fallback would score lower. This slice only
# emits structured rows, but the seam is here for the later fallback layers.
CONFIDENCE_STRUCTURED = 0.9
CONFIDENCE_LOOSE = 0.6

PRODUCER = {"program": 1, "app_version": "0.1.0", "agent_id": "scraper"}
SUGGESTED_CATEGORY_FIELD = "suggested_category"

_SCHEMA_CACHE: list = []


def _cached_schemas() -> list:
    if not _SCHEMA_CACHE:
        _SCHEMA_CACHE.extend(load_schemas())
    return _SCHEMA_CACHE


def _record_id(fields: dict, page_url: str) -> str:
    """Stable per-product id: prefer the product's SKU, else the URL slug."""
    sku = fields.get("sku")
    if sku:
        return str(sku)
    path = urlparse(page_url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if path else ""
    return slug or urlparse(page_url).netloc


def to_evidence_rows(
    fields: dict, page_url: str, *, structured: bool = True
) -> list[EvidenceRow]:
    """Convert one page's discovered fields into EvidenceRows.

    One row per field that has a value; a field with no value yields no row.
    source_uri is the exact page URL, method is 'scrape'. Nothing is invented.
    """
    record_id = _record_id(fields, page_url)
    confidence = CONFIDENCE_STRUCTURED if structured else CONFIDENCE_LOOSE
    rows: list[EvidenceRow] = []
    for field_name, value in fields.items():
        if value is None or str(value).strip() == "":
            continue
        rows.append(
            EvidenceRow(
                record_id=record_id,
                field=field_name,
                value=str(value),
                source_uri=page_url,
                method="scrape",
                confidence=confidence,
            )
        )
    return rows


def classification_rows(
    fields: dict, page_url: str, *, schemas: list | None = None
) -> list[EvidenceRow]:
    """Zero or one 'suggested_category' row from the product's name+description.

    A complementary content-based signal to field-name matching. Emits a single
    row only when the tie-resolved top classification clears CLASSIFY_THRESHOLD;
    below threshold (or with no name/description, or no schema store) nothing is
    emitted — a real absence, not a forced guess. When several categories tie at
    the top score, the value is their shared family prefix, not an arbitrary leaf.
    No existing field's row is touched.
    """
    product_text = " ".join(
        str(fields[key]) for key in ("name", "description") if fields.get(key)
    ).strip()
    if not product_text:
        return []
    if schemas is None:
        schemas = _cached_schemas()
    if not schemas:
        return []

    suggestion = top_suggestion(classify_category(product_text, schemas))
    if (
        suggestion is None
        or suggestion.score < CLASSIFY_THRESHOLD
        or not suggestion.category_path
    ):
        return []
    return [
        EvidenceRow(
            record_id=_record_id(fields, page_url),
            field=SUGGESTED_CATEGORY_FIELD,
            value=" > ".join(suggestion.category_path),
            source_uri=page_url,
            method="scrape",
            confidence=suggestion.score,
        )
    ]


def build_pack_from_fields(
    fields: dict,
    page_url: str,
    output_path: str,
    *,
    structured: bool = True,
    schemas: list | None = None,
) -> list[EvidenceRow]:
    """Build a BK-PACK at output_path from one page's discovered fields.

    Returns the evidence rows written. If the page yielded no usable fields, no
    pack is built and an empty list is returned (never an empty/fabricated pack).
    A single content-based 'suggested_category' row may be appended (see
    classification_rows); no other row is changed.
    """
    rows = to_evidence_rows(fields, page_url, structured=structured)
    if not rows:
        return []
    rows = rows + classification_rows(fields, page_url, schemas=schemas)
    build_bkpack(
        output_path=output_path,
        evidence_rows=rows,
        media_files={},
        producer=PRODUCER,
    )
    return rows
