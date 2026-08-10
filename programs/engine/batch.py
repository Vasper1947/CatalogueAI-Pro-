"""Batch orchestration: N staged records -> one detect + populate pass each ->
grouped-by-category .xlsx file(s), respecting each schema's real row_limit
(splitting into multiple files beyond it). Failed/ambiguous records are never
silently dropped and never written as a half-row — every record lands in
exactly one outcome bucket in the returned BatchRunSummary, and a chunk whose
write fails self-verification is reported, not raised past the batch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from engine.detect import match_template
from engine.populate import populate_from_evidence
from engine.variants import VariantExpansion, expand_variants
from engine.writer import RowWriteResult, WriteVerificationError, write_template_batch

# Fallback only for the pathological case of a schema whose Instructions
# sheet stated no row limit at all -- every real schema seen in this project
# states one explicitly (500, on every category checked so far).
DEFAULT_ROW_LIMIT = 500


@dataclass
class RecordOutcome:
    record_id: str
    status: str  # "matched" | "no_template_match" | "category_ambiguous"
    category_path: list[str] | None = None
    confidence: float = 0.0
    reason: str | None = None  # human-readable detail for the non-matched cases


@dataclass
class WrittenFile:
    output_path: str
    category_path: list[str]
    record_ids: list[str]
    row_results: list[RowWriteResult]


@dataclass
class WriteFailure:
    category_path: list[str]
    record_ids: list[str]
    error: str


@dataclass
class BatchRunSummary:
    total_records: int
    matched: list[RecordOutcome] = field(default_factory=list)
    no_template_match: list[RecordOutcome] = field(default_factory=list)
    category_ambiguous: list[RecordOutcome] = field(default_factory=list)
    written_files: list[WrittenFile] = field(default_factory=list)
    write_failures: list[WriteFailure] = field(default_factory=list)
    # One entry per matched record that actually had a variant field expanded
    # (see engine.variants.expand_variants) -- empty unless expand_variants=True.
    variant_expansions: list[VariantExpansion] = field(default_factory=list)


def _slug(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return safe or "category"


def _row_limit(schema: dict) -> int:
    limit = (schema.get("instructions") or {}).get("row_limit")
    return int(limit) if limit else DEFAULT_ROW_LIMIT


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]


def run_batch(
    records: list[tuple[str, list[dict]]],
    schemas: list[dict],
    output_dir,
    *,
    base_filename: str = "products",
    forced_schema: dict | None = None,
    expand_variants_flag: bool = False,
) -> BatchRunSummary:
    """records: [(record_id, evidence_rows_as_dicts), ...] -- typically one
    entry per staged product (see export.staging.load_staged_evidence_rows).

    For each record: run detect (match_template) then, on a match, populate
    (populate_from_evidence). Records that fail to match a template, or land
    in a genuine unresolved category tie, are recorded in the summary and
    excluded from every written file -- never dropped silently, never forced
    into a guessed category.

    ``forced_schema``, when given, is a human's explicit override (e.g. the
    CLI's --category-override) of automatic detection: every record is
    treated as matched to this exact schema, skipping match_template
    entirely. This is a deliberate manual decision, not a guess dressed up as
    one -- it exists for the real case where a human already knows the
    correct BK category and match_template's own thresholds are getting in
    the way (e.g. a genuine ambiguous_tie the evidence itself cannot resolve).

    Matched records are grouped by their detected category_path (one schema
    = one set of columns = one file), then each group is chunked to at most
    that schema's real row_limit (its Instructions sheet's stated cap, e.g.
    500) and written via engine.writer.write_template_batch, one .xlsx per
    chunk. A chunk whose mandatory self-verification fails is recorded in
    write_failures rather than raising past the whole batch run -- one bad
    chunk must not lose every other already-verified file.

    ``expand_variants_flag``, when True, runs each matched record's
    PopulationResult through engine.variants.expand_variants before grouping:
    a record with a real multi-option field (e.g. "Color: Silver/Golden/
    Bronze") becomes N rows, one real option per row, instead of one row with
    that field left an unresolved variant_candidate. Off by default -- this
    changes row counts, so it is an explicit, human-controlled decision, not
    an automatic behavior change.
    """
    summary = BatchRunSummary(total_records=len(records))
    groups: dict[tuple, list[tuple[str, object]]] = {}
    schema_by_path: dict[tuple, dict] = {}

    for record_id, evidence in records:
        if forced_schema is not None:
            best, confidence = forced_schema, 1.0
        else:
            best, confidence, candidates = match_template(evidence, schemas)
            tied = [c for c in candidates if c.ambiguous_tie]
            if tied:
                summary.category_ambiguous.append(
                    RecordOutcome(
                        record_id=record_id, status="category_ambiguous", confidence=confidence,
                        reason=(
                            f"unresolved tie among {len(tied)} candidates "
                            f"at precision {confidence:.3f}"
                        ),
                    )
                )
                continue
        if best is None:
            summary.no_template_match.append(
                RecordOutcome(
                    record_id=record_id, status="no_template_match", confidence=confidence,
                    reason="no schema cleared the match/recall thresholds",
                )
            )
            continue

        category_path = best["category_path"]
        summary.matched.append(
            RecordOutcome(
                record_id=record_id, status="matched",
                category_path=category_path, confidence=confidence,
            )
        )
        key = tuple(category_path)
        schema_by_path[key] = best
        population = populate_from_evidence(evidence, best)

        if expand_variants_flag:
            population_rows, expansion = expand_variants(record_id, population)
            if expansion.expanded_field is not None:
                summary.variant_expansions.append(expansion)
        else:
            population_rows = [population]

        for pop in population_rows:
            groups.setdefault(key, []).append((record_id, pop))

    output_dir = Path(output_dir)
    for key, entries in groups.items():
        schema = schema_by_path[key]
        limit = _row_limit(schema)
        chunks = _chunk(entries, limit)
        category_slug = _slug("_".join(key))
        multi = len(chunks) > 1
        for part, chunk_entries in enumerate(chunks, start=1):
            if not chunk_entries:
                continue
            record_ids = [rid for rid, _pop in chunk_entries]
            population_results = [pop for _rid, pop in chunk_entries]
            suffix = f"_part{part}" if multi else ""
            output_path = output_dir / f"{base_filename}__{category_slug}{suffix}.xlsx"
            try:
                batch_result = write_template_batch(population_results, schema, output_path)
            except WriteVerificationError as exc:
                summary.write_failures.append(
                    WriteFailure(category_path=list(key), record_ids=record_ids, error=str(exc))
                )
                continue
            summary.written_files.append(
                WrittenFile(
                    output_path=str(output_path), category_path=list(key),
                    record_ids=record_ids, row_results=batch_result.row_results,
                )
            )

    return summary
