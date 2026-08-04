"""Assemble researched findings into a category's domain knowledge.

The genuine web research and judgment happen upstream (a human/agent runs real
web searches and decides what is credible). ``research_category`` is the
deterministic seam that records those findings honestly: it keeps a fact only
when it (a) references a field that actually exists in the category's schema and
(b) carries a source URL. It never invents a field the schema does not have,
never records an unsourced fact, and always starts a freshly-researched category
as ``pending_review``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from domain_knowledge.models import (
    REVIEW_PENDING,
    CategoryKnowledge,
    PlausibleRange,
    Standard,
    TerminologyEntry,
)


def _schema_field_names(schema) -> set[str]:
    fields = schema.get("fields") if isinstance(schema, dict) else getattr(schema, "fields", [])
    names: set[str] = set()
    for f in fields or []:
        name = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
        if name:
            names.add(name)
    return names


def research_category(category_path, schema, findings: dict, *, researched_at: str | None = None):
    """Build a pending-review CategoryKnowledge from grounded, sourced findings.

    ``findings`` = {
        "plausible_ranges": [{"field","min","max","unit","source_url"}, ...],
        "standards":        [{"name","description","source_url"}, ...],
        "terminology":      [{"synonym","canonical_term","source_url"}, ...],
    }
    A range whose field is not in the schema, or any fact lacking a source_url,
    is dropped — never invented, never unsourced.
    """
    schema_fields = _schema_field_names(schema)

    plausible_ranges: dict[str, PlausibleRange] = {}
    for entry in findings.get("plausible_ranges") or []:
        field_name = entry.get("field")
        source = entry.get("source_url")
        if not field_name or field_name not in schema_fields or not source:
            continue
        if entry.get("min") is None or entry.get("max") is None:
            continue
        plausible_ranges[field_name] = PlausibleRange(
            min=float(entry["min"]),
            max=float(entry["max"]),
            unit=entry.get("unit"),
            source_url=source,
        )

    standards = [
        Standard(
            name=item["name"],
            description=item.get("description", ""),
            source_url=item["source_url"],
        )
        for item in (findings.get("standards") or [])
        if item.get("name") and item.get("source_url")
    ]

    terminology: dict[str, TerminologyEntry] = {}
    for item in findings.get("terminology") or []:
        synonym = item.get("synonym")
        canonical = item.get("canonical_term")
        source = item.get("source_url")
        if synonym and canonical and source:
            terminology[synonym] = TerminologyEntry(
                canonical_term=canonical, source_url=source
            )

    return CategoryKnowledge(
        category_path=list(category_path),
        plausible_ranges=plausible_ranges,
        standards=standards,
        terminology=terminology,
        researched_at=researched_at or datetime.now(UTC).isoformat(),
        review_status=REVIEW_PENDING,
    )
