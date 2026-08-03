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

# Confidence reflects provenance: schema.org JSON-LD is high-trust structured
# data; a looser (non-structured) fallback would score lower. This slice only
# emits structured rows, but the seam is here for the later fallback layers.
CONFIDENCE_STRUCTURED = 0.9
CONFIDENCE_LOOSE = 0.6

PRODUCER = {"program": 1, "app_version": "0.1.0", "agent_id": "scraper"}


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


def build_pack_from_fields(
    fields: dict, page_url: str, output_path: str, *, structured: bool = True
) -> list[EvidenceRow]:
    """Build a BK-PACK at output_path from one page's discovered fields.

    Returns the evidence rows written. If the page yielded no usable fields, no
    pack is built and an empty list is returned (never an empty/fabricated pack).
    """
    rows = to_evidence_rows(fields, page_url, structured=structured)
    if not rows:
        return []
    build_bkpack(
        output_path=output_path,
        evidence_rows=rows,
        media_files={},
        producer=PRODUCER,
    )
    return rows
