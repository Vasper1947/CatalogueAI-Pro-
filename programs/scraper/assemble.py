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
from domain_knowledge.check import check_plausibility
from domain_knowledge.store import find_knowledge
from schemas.classify import (
    CLASSIFY_THRESHOLD,
    classify_category,
    load_schemas,
    top_suggestion,
)

from scraper.discover import extract_spec_table
from scraper.units import normalize_value

# Confidence reflects provenance / extraction path. A spec table's explicit
# key/value rows are the highest-trust scrape signal, above schema.org JSON-LD;
# a looser (non-structured) fallback scores lower. A spec value whose unit
# normalization was ambiguous is dropped to an "uncertain" tier rather than
# carrying the full spec-table confidence.
CONFIDENCE_SPEC_TABLE = 0.95
CONFIDENCE_SPEC_TABLE_UNCERTAIN = 0.4
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


def _top_category_suggestion(fields: dict, schemas: list | None):
    """The tie-resolved top category for a product, or None below threshold.

    Shared by the suggested_category row and the plausibility lookup.
    """
    product_text = " ".join(
        str(fields[key]) for key in ("name", "description") if fields.get(key)
    ).strip()
    if not product_text:
        return None
    if schemas is None:
        schemas = _cached_schemas()
    if not schemas:
        return None
    suggestion = top_suggestion(classify_category(product_text, schemas))
    if (
        suggestion is None
        or suggestion.score < CLASSIFY_THRESHOLD
        or not suggestion.category_path
    ):
        return None
    return suggestion


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
    suggestion = _top_category_suggestion(fields, schemas)
    if suggestion is None:
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


def _clean_key(key: str) -> str:
    return " ".join(key.split()).rstrip(":").strip()


def _num_str(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _format_value(normalized: object, unit: str | None) -> str:
    if isinstance(normalized, list):
        body = " x ".join(_num_str(n) for n in normalized)
        return f"{body} {unit}" if unit else body
    if isinstance(normalized, (int, float)):
        return f"{_num_str(normalized)} {unit}" if unit else _num_str(normalized)
    return str(normalized)


def spec_table_rows(
    page_html: str, page_url: str, *, record_id: str
) -> list[EvidenceRow]:
    """One EvidenceRow per spec-table key/value, unit-normalized.

    Spec-table values carry a higher confidence tier than generic JSON-LD
    fields. A value whose unit normalization was ambiguous is flagged at the
    uncertain tier and kept as its original text — never dropped, never guessed.
    Existing JSON-LD row building is untouched.
    """
    rows: list[EvidenceRow] = []
    for key, raw in extract_spec_table(page_html):
        field = _clean_key(key)
        normalized, unit, norm_confidence = normalize_value(raw)
        value = _format_value(normalized, unit)
        if not field or not value.strip():
            continue
        confidence = (
            CONFIDENCE_SPEC_TABLE
            if norm_confidence >= 0.5
            else CONFIDENCE_SPEC_TABLE_UNCERTAIN
        )
        rows.append(
            EvidenceRow(
                record_id=record_id,
                field=field,
                value=value,
                source_uri=page_url,
                method="scrape",
                confidence=confidence,
            )
        )
    return rows


def build_pack_from_fields(
    fields: dict,
    page_url: str,
    output_path: str,
    *,
    structured: bool = True,
    schemas: list | None = None,
    page_html: str | None = None,
) -> list[EvidenceRow]:
    """Build a BK-PACK at output_path from one page's discovered fields.

    Returns the evidence rows written. If the page yielded no usable fields, no
    pack is built and an empty list is returned (never an empty/fabricated pack).
    A single content-based 'suggested_category' row may be appended (see
    classification_rows), and — when ``page_html`` is supplied — spec-table rows
    (see spec_table_rows). No existing JSON-LD-derived row is changed.
    """
    rows = to_evidence_rows(fields, page_url, structured=structured)
    if not rows:
        return []
    record_id = _record_id(fields, page_url)
    rows = rows + classification_rows(fields, page_url, schemas=schemas)
    if page_html:
        rows = rows + spec_table_rows(page_html, page_url, record_id=record_id)
    build_bkpack(
        output_path=output_path,
        evidence_rows=rows,
        media_files={},
        producer=PRODUCER,
    )
    return rows


def plausibility_checks(field_values, knowledge) -> list[dict]:
    """Flag each (field, value) against domain knowledge — a PARALLEL structure.

    Returns one {field, value, verdict, source} per input. It never touches,
    reorders, or drops any EvidenceRow, and is never written into the BK-PACK.
    ``knowledge=None`` -> every verdict is "unknown". An "implausible" verdict is
    only a flag for a human / Program 3 — it changes no value anywhere.
    """
    ranges = getattr(knowledge, "plausible_ranges", None) or {}
    results: list[dict] = []
    for field_name, value in field_values:
        verdict = check_plausibility(field_name, value, knowledge)
        source = None
        if verdict in ("plausible", "implausible"):
            entry = ranges.get(field_name)
            source = getattr(entry, "source_url", None) if entry is not None else None
        results.append(
            {"field": field_name, "value": str(value), "verdict": verdict, "source": source}
        )
    return results


def _confirmed_knowledge(category_path, data_dir):
    """Domain knowledge for a category, but only if a human has confirmed it."""
    knowledge = (
        find_knowledge(category_path)
        if data_dir is None
        else find_knowledge(category_path, data_dir)
    )
    if knowledge is None or getattr(knowledge, "review_status", None) != "confirmed":
        return None
    return knowledge


def plausibility_report(
    fields: dict,
    page_url: str,
    *,
    page_html: str | None = None,
    schemas: list | None = None,
    data_dir=None,
) -> list[dict]:
    """Parallel plausibility flags for a page's extracted fields.

    Classifies the product, looks up CONFIRMED domain knowledge for that category
    (a family/leaf prefix match is allowed), and flags each extracted field —
    from the JSON-LD fields and the spec table. A category with no confirmed
    knowledge (509 of 510 today) yields "unknown" for every field, silently, not
    an error. EvidenceRows are never touched; this list is entirely separate.
    """
    suggestion = _top_category_suggestion(fields, schemas)
    knowledge = (
        _confirmed_knowledge(suggestion.category_path, data_dir) if suggestion else None
    )

    field_values: list[tuple[str, str]] = []
    for field_name, value in fields.items():
        if value is not None and str(value).strip():
            field_values.append((field_name, str(value)))
    if page_html:
        for key, raw in extract_spec_table(page_html):
            field_name = _clean_key(key)
            normalized, unit, _ = normalize_value(raw)
            value = _format_value(normalized, unit)
            if field_name and value.strip():
                field_values.append((field_name, value))

    return plausibility_checks(field_values, knowledge)
