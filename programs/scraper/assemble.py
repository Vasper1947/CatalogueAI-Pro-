"""Assemble discovered fields into a BK-PACK using packages/bkpack as-is.

Each field that structured data actually provided becomes one EvidenceRow whose
source_uri is the exact page URL it was read from. A field the page did not
provide simply has no row — it is never filled with a guess. The rows are handed
to build_bkpack() from packages/bkpack, which is used exactly as it already
exists (no changes to that package).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from common.units import normalize_value
from domain_knowledge.check import check_plausibility
from domain_knowledge.store import find_knowledge
from export.staging import stage_capture
from schemas.aliases import resolve_field
from schemas.classify import (
    CLASSIFY_THRESHOLD,
    classify_category,
    load_schemas,
    top_suggestion,
)

from scraper.discover import (
    extract_page_metadata,
    extract_spec_table,
    find_media,
    metadata_to_fields,
)

# Confidence reflects provenance / extraction path. A spec table's explicit
# key/value rows are the highest-trust scrape signal, above schema.org JSON-LD;
# a looser (non-structured) fallback scores lower. A spec value whose unit
# normalization was ambiguous is dropped to an "uncertain" tier rather than
# carrying the full spec-table confidence.
CONFIDENCE_SPEC_TABLE = 0.95
CONFIDENCE_SPEC_TABLE_UNCERTAIN = 0.4
CONFIDENCE_STRUCTURED = 0.9
# Page metadata (Open Graph / Twitter Card / <title>/<h1>/meta description --
# see metadata_fallback_rows) is real, human-authored page-summary text, not
# a guess, but it is a general SEO/social-share signal, not schema.org
# Product markup specifically about this item -- less authoritative than
# JSON-LD. This is exactly the "looser (non-structured) fallback" this tier
# was already reserved for above; metadata_fallback_rows is its first use.
CONFIDENCE_LOOSE = 0.6
# A Brand inferred by a whole-word hit against the schema's own closed Brand
# vocabulary. Above the loose text fallback (0.6, unconstrained free text) because
# the value is constrained to a known brand set; below an author-declared Brand
# field (JSON-LD 0.9 / spec-table 0.95) because it is inferred from prose position,
# not a field the source labelled "Brand".
CONFIDENCE_VOCABULARY = 0.7

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


def metadata_fallback_rows(
    jsonld_fields: dict, metadata_fields: dict, page_url: str, *, record_id: str
) -> list[EvidenceRow]:
    """name/description EvidenceRows sourced from page metadata (see
    scraper.discover.extract_page_metadata/metadata_to_fields) -- ONLY for a
    field JSON-LD did not already provide; a JSON-LD value is NEVER
    overridden. Tagged at CONFIDENCE_LOOSE (see that constant's own
    reasoning). This is the root-cause fix for pages with no Product JSON-LD
    at all: previously such pages contributed no name/description evidence
    whatsoever, which meant no content signal for classify_category or
    detect.py's content tie-break, and Brand was never inferable from
    product text either.
    """
    rows: list[EvidenceRow] = []
    for field_name in ("name", "description"):
        if jsonld_fields.get(field_name):
            continue  # JSON-LD already has it -- never overridden
        value = metadata_fields.get(field_name)
        if value:
            rows.append(
                EvidenceRow(
                    record_id=record_id, field=field_name, value=value,
                    source_uri=page_url, method="scrape", confidence=CONFIDENCE_LOOSE,
                )
            )
    return rows


def match_brand_from_vocabulary(
    product_text, schema, *, source_uri: str, record_id: str
) -> EvidenceRow | None:
    """Infer a Brand from the schema's own Lookup:Brand vocabulary.

    Cross-references each brand in ``schema["lookups"]["Brand"]`` against the
    product text, case-insensitive and WHOLE-WORD (no substring, no fuzzy). The
    first vocabulary brand present as a whole word yields a Brand EvidenceRow
    sourced to the page. A schema with no Brand vocabulary (e.g. a free-text Brand
    field, as the TMT schemas have) or no hit yields None.

    ``source_uri`` / ``record_id`` are required because every EvidenceRow value
    must carry provenance — they are the page URL and product id, not part of the
    matching logic itself.

    Caveat: the vocabulary is the schema's as-is. A generic list may contain
    common words (e.g. "India"); a whole-word hit on such a token is a real match
    per this rule but a vocabulary-quality risk, not a bug here.
    """
    vocab = (schema.get("lookups") or {}).get("Brand") or []
    text = str(product_text or "")
    if not vocab or not text.strip():
        return None
    for brand in vocab:
        b = str(brand).strip()
        if b and re.search(r"\b" + re.escape(b) + r"\b", text, flags=re.IGNORECASE):
            return EvidenceRow(
                record_id=record_id,
                field="Brand",
                value=b,
                source_uri=source_uri,
                method="scrape",
                confidence=CONFIDENCE_VOCABULARY,
            )
    return None


def _schema_for_path(category_path, schemas):
    target = list(category_path)
    for s in schemas:
        if list(s.get("category_path", [])) == target:
            return s
    return None


def brand_vocab_rows(
    fields: dict, page_url: str, *, schemas: list | None = None
) -> list[EvidenceRow]:
    """Zero or one Brand row inferred from the top-suggested category's vocabulary.

    Fires only when the product classifies to a single leaf category (not a tied
    family prefix) whose schema declares a Brand vocabulary, and a vocabulary
    brand appears whole-word in the product's name+description. Emits nothing
    otherwise — a real absence, never a guess.
    """
    suggestion = _top_category_suggestion(fields, schemas)
    if suggestion is None:
        return []
    pool = schemas if schemas is not None else _cached_schemas()
    schema = _schema_for_path(suggestion.category_path, pool)
    if schema is None:  # tied family prefix, or no matching leaf schema
        return []
    text = " ".join(
        str(fields[k]) for k in ("name", "description") if fields.get(k)
    ).strip()
    row = match_brand_from_vocabulary(
        text, schema, source_uri=page_url, record_id=_record_id(fields, page_url)
    )
    return [row] if row is not None else []


def build_pack_from_fields(
    fields: dict,
    page_url: str,
    output_path: str,
    *,
    structured: bool = True,
    schemas: list | None = None,
    page_html: str | None = None,
    job_id: str | None = None,
    staging_root=None,
    image_bytes_list: list[bytes] | None = None,
) -> list[EvidenceRow]:
    """Build a BK-PACK at output_path from one page's discovered fields.

    Returns the evidence rows written. If the page yielded no usable fields, no
    pack is built and an empty list is returned (never an empty/fabricated pack).
    "No usable fields" means neither JSON-LD-derived rows NOR spec-table rows —
    the two sources are gathered independently and only their COMBINATION
    decides whether there is anything to build a pack from. A page with a real
    spec table but no JSON-LD (e.g. no Product-typed structured data at all)
    now stages exactly that spec-table data, the same way a page with JSON-LD
    but no spec table already staged that. A single content-based
    'suggested_category' row may also be appended (see classification_rows).
    No existing JSON-LD-derived row is changed.

    When ``job_id`` is given, the assembled rows (and any ``image_bytes_list``
    — a full-page snapshot, if the caller captured one, is just another entry
    here, staged with the same discipline as a product photo) are ALSO written
    immediately to crash-safe staging (packages/export.staging.stage_capture)
    before the in-memory pack below is built — this is the "no data lost ever"
    mechanism: the capture is safe on disk the instant this call reaches that
    point, independent of whether build_bkpack below (or the rest of the run)
    ever completes. Any video/gif references discoverable in ``page_html``
    (scraper.discover.find_media) are staged alongside as metadata. Omitting
    ``job_id`` preserves the exact prior behaviour (no staging at all) — fully
    backward compatible.
    """
    record_id = _record_id(fields, page_url)
    json_ld_rows = to_evidence_rows(fields, page_url, structured=structured)
    spec_rows = spec_table_rows(page_html, page_url, record_id=record_id) if page_html else []
    if not json_ld_rows and not spec_rows:
        # No product-shaped evidence at all -- page metadata (a <title>, a
        # meta description) exists on almost every real page, product or
        # not, so it must never be what DECIDES a page is capturable, only
        # what ENRICHES a page that already qualified via JSON-LD or a real
        # spec table. Without this gate, a blog/about/nav page would get
        # "captured" off its SEO tags alone.
        return []
    # Page metadata (Open Graph/Twitter Card/<title>/<h1>/meta description)
    # fills name/description ONLY when JSON-LD provided neither -- see
    # metadata_fallback_rows. This is the root-cause fix for a REAL product
    # page with no Product JSON-LD at all (confirmed by the spec_rows check
    # above): it used to contribute zero name/description evidence, so
    # classify_category, the Brand-vocabulary text match, and detect.py's
    # content tie-break all had nothing to search.
    metadata_fields = metadata_to_fields(extract_page_metadata(page_html, page_url)) if page_html else {}
    meta_rows = metadata_fallback_rows(fields, metadata_fields, page_url, record_id=record_id)
    rows = json_ld_rows + spec_rows + meta_rows
    # classify_category/brand-vocab matching (inside classification_rows/
    # brand_vocab_rows) key off name/description -- merge metadata's fallback
    # in too (JSON-LD's own value always wins on overlap, same rule as the
    # evidence rows above), so a spec-table-only page's real page title/
    # description is real content to classify and content-tie-break against.
    classification_fields = {**metadata_fields, **fields}
    rows = rows + classification_rows(classification_fields, page_url, schemas=schemas)
    # Infer Brand from the category's vocabulary, but only if the page did not
    # already provide a Brand field of its own (no overwrite, no duplicate).
    if not any(r.field.strip().lower() == "brand" for r in rows):
        rows = rows + brand_vocab_rows(classification_fields, page_url, schemas=schemas)
    if job_id is not None:
        media_refs = find_media(page_html, page_url) if page_html else []
        stage_capture(
            job_id, record_id, rows, image_bytes_list or [],
            staging_root=staging_root, media_refs=media_refs or None,
        )
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
    available = set(ranges)
    results: list[dict] = []
    for field_name, value in field_values:
        # A field-name alias (e.g. a Diameter value keyed "Size") resolves to the
        # researched field before lookup; the observed name is still reported.
        resolved = resolve_field(field_name, value, available_fields=available)
        verdict = check_plausibility(resolved, value, knowledge)
        source = None
        if verdict in ("plausible", "implausible"):
            entry = ranges.get(resolved)
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
