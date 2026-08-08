"""Crash-safe staging of scrape captures, ahead of any ZIP packaging.

This is the actual "no data lost ever" mechanism: stage_capture() writes a
record's evidence and raw image bytes to disk immediately, before any
in-memory BK-PACK is assembled. A capture is safe the instant stage_capture()
returns, independent of whether the run that made it ever finishes.
finalize_zip() (added alongside write_sku_csv, see csv_export.py) can then be
called at the natural end of a run, or much later against leftover staged
data from a run that never finished — same function either way, same result,
because it only ever reads what is actually on disk under a job_id.

Layout under a caller-supplied staging_root (never a hardcoded, repo-relative
default — see the module docstring in __init__.py):
    <staging_root>/<job_id>/<record_id>/evidence.jsonl
    <staging_root>/<job_id>/<record_id>/image_<n>.raw
    <staging_root>/<job_id>/<record_id>/<record_id>_<n>.webp   (after processing)
    <staging_root>/<job_id>/<record_id>/media_refs.json        (discovered video/gif URLs, if any)

A full-page snapshot is not a distinct staging concept — it is just another
image (PNG bytes), staged and processed through the exact same image_bytes_list
/ process_image path as a product photo, per Task 4's "same crash-safe
discipline as images."
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from bkpack.evidence import EvidenceRow, read_evidence_jsonl, write_evidence_jsonl
from bkpack.writer import build_bkpack

from export.images import process_image


def _record_dir(job_id: str, record_id: str, staging_root) -> Path:
    return Path(staging_root) / job_id / record_id


def stage_capture(
    job_id: str,
    record_id: str,
    evidence_rows: list[EvidenceRow],
    image_bytes_list: list[bytes],
    *,
    staging_root,
    media_refs: list[dict] | None = None,
) -> Path:
    """Write one record's evidence and raw image bytes to disk immediately.

    evidence_rows are already-validated EvidenceRow objects (EvidenceRow
    raises at construction on any "no evidence, no value" violation — never
    re-checked here, because it can't be false by the time this runs).
    ``media_refs`` (optional) is discovered video/gif URL metadata (see
    discover.find_media) — references, not bytes, so it is written as a small
    JSON file rather than staged like an image. Returns the record's staging
    directory.
    """
    record_dir = _record_dir(job_id, record_id, staging_root)
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / "evidence.jsonl").write_text(
        write_evidence_jsonl(evidence_rows), encoding="utf-8"
    )
    for index, raw_bytes in enumerate(image_bytes_list):
        (record_dir / f"image_{index}.raw").write_bytes(raw_bytes)
    if media_refs:
        (record_dir / "media_refs.json").write_text(
            json.dumps(media_refs, indent=2), encoding="utf-8"
        )
    return record_dir


def list_staged_records(job_id: str, *, staging_root) -> list[str]:
    """Every record currently staged for a job, sorted -- what's actually on
    disk right now, so a run can resume/finalize from wherever it was left."""
    job_dir = Path(staging_root) / job_id
    if not job_dir.exists():
        return []
    return sorted(p.name for p in job_dir.iterdir() if p.is_dir())


def load_staged_evidence_rows(job_id: str, record_id: str, *, staging_root) -> list[EvidenceRow]:
    """Read one record's staged evidence.jsonl back into real EvidenceRow
    objects (re-validated at construction -- defense in depth against a
    hand-edited or corrupted staging file, same discipline as bkpack itself)."""
    path = _record_dir(job_id, record_id, staging_root) / "evidence.jsonl"
    rows = read_evidence_jsonl(path.read_text(encoding="utf-8"))
    return [EvidenceRow(**row) for row in rows]


def _process_staged_images(job_id: str, record_id: str, staging_root) -> None:
    """Convert any of a record's staged raw images that don't yet have a
    corresponding WebP. Idempotent: an already-processed image is skipped, so
    calling finalize_zip twice against the same staged data never re-does
    (or duplicates) the work."""
    record_dir = _record_dir(job_id, record_id, staging_root)
    for raw_path in sorted(record_dir.glob("image_*.raw")):
        index = int(raw_path.stem.split("_", 1)[1])
        webp_path = record_dir / f"{record_id}_{index}.webp"
        if not webp_path.exists():
            process_image(record_id, index, raw_path.read_bytes(), output_dir=record_dir)


def finalize_zip(job_id: str, output_path, *, staging_root, producer: dict) -> Path:
    """Build the final BK-PACK ZIP for a job from whatever is currently
    staged on disk -- callable at the natural end of a run, or later, standing
    alone, against leftover staged data from a run that never finished. Same
    function either way, because it never depends on anything beyond job_id
    and what stage_capture() already wrote to staging_root.

    1. Process any not-yet-converted staged images (idempotent) -- this
       includes a full-page snapshot, since it is staged as just another image.
    2. Call the existing, UNMODIFIED bkpack.writer.build_bkpack() for the core
       pack (datapackage.json/evidence.jsonl/manifest/media) -- packages/bkpack
       is only ever called here, never reimplemented.
    3. Generate SKU.csv (export.csv_export.write_sku_csv) from the same staged
       evidence, and append it to the just-built ZIP.
    4. If any record staged discovered video/gif references (media_refs.json),
       aggregate them (keyed by record_id, same aggregation pattern as
       SKU.csv) into one media_refs.json at the ZIP root. Omitted entirely
       when no record staged any -- never an empty/fabricated file.
    """
    from export.csv_export import write_sku_csv  # deferred: csv_export imports
    # list_staged_records from this module; a module-level import here would
    # be circular between these two sibling modules.

    record_ids = list_staged_records(job_id, staging_root=staging_root)

    all_rows: list[EvidenceRow] = []
    media_files: dict[str, bytes] = {}
    all_media_refs: dict[str, list[dict]] = {}
    for record_id in record_ids:
        _process_staged_images(job_id, record_id, staging_root)
        all_rows.extend(
            load_staged_evidence_rows(job_id, record_id, staging_root=staging_root)
        )
        record_dir = _record_dir(job_id, record_id, staging_root)
        for webp_path in sorted(record_dir.glob("*.webp")):
            media_files[webp_path.name] = webp_path.read_bytes()
        refs_path = record_dir / "media_refs.json"
        if refs_path.exists():
            all_media_refs[record_id] = json.loads(refs_path.read_text(encoding="utf-8"))

    build_bkpack(
        output_path=str(output_path),
        evidence_rows=all_rows,
        media_files=media_files,
        producer=producer,
    )

    csv_text = write_sku_csv(job_id, staging_root=staging_root)
    with zipfile.ZipFile(output_path, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKU.csv", csv_text)
        if all_media_refs:
            zf.writestr("media_refs.json", json.dumps(all_media_refs, indent=2))

    return Path(output_path)
