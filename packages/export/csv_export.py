"""CSV generation FROM staged evidence -- never an independent path that
could diverge from it. A field's value, when present, comes directly from
the evidence ledger; a field a record's evidence doesn't have is a blank
cell, never guessed or fabricated.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from bkpack.evidence import read_evidence_jsonl

from export.staging import list_staged_records

IMAGES_COLUMN = "images"
_IMAGE_NAME_SEP = "; "


def _record_dir(job_id: str, record_id: str, staging_root) -> Path:
    return Path(staging_root) / job_id / record_id


def _record_field_values(job_id: str, record_id: str, staging_root) -> dict[str, str]:
    """canonical-free {field name -> value} for one staged record, straight
    from its evidence.jsonl -- an absence row (value=None) contributes
    nothing, leaving that field's cell blank, exactly like a never-captured
    field."""
    path = _record_dir(job_id, record_id, staging_root) / "evidence.jsonl"
    rows = read_evidence_jsonl(path.read_text(encoding="utf-8"))
    values: dict[str, str] = {}
    for row in rows:
        value = row.get("value")
        if value is not None:
            values.setdefault(row["field"], str(value))
    return values


def _record_image_names(job_id: str, record_id: str, staging_root) -> list[str]:
    """Already-processed WebP filenames for a record (see images.py) -- this
    module never calls process_image itself; it only reads whatever the
    staging directory already contains, kept decoupled from image processing."""
    record_dir = _record_dir(job_id, record_id, staging_root)
    return sorted(p.name for p in record_dir.glob("*.webp"))


def write_sku_csv(job_id: str, *, staging_root) -> str:
    """One CSV row per staged record. Columns = "record_id" + the sorted
    union of fields actually present across every record in the job +
    "images" (a semicolon-joined list of that record's processed WebP
    filenames). Every value is read directly from the record's staged
    evidence -- there is no other source."""
    record_ids = list_staged_records(job_id, staging_root=staging_root)
    per_record = {rid: _record_field_values(job_id, rid, staging_root) for rid in record_ids}

    field_names: set[str] = set()
    for values in per_record.values():
        field_names.update(values)
    columns = ["record_id", *sorted(field_names), IMAGES_COLUMN]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    for record_id in record_ids:
        row = {"record_id": record_id, **per_record[record_id]}
        row[IMAGES_COLUMN] = _IMAGE_NAME_SEP.join(
            _record_image_names(job_id, record_id, staging_root)
        )
        writer.writerow(row)
    return buf.getvalue()
