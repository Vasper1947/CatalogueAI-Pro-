"""Crash-safe staging: a capture is safe on disk the instant stage_capture()
returns, independent of whether the run ever finishes. staging_root is always
an explicit parameter (never a hardcoded repo-relative default) — tests use
tmp_path, so nothing ever touches the git tree.
"""

import json

from bkpack.evidence import EvidenceRow
from export.staging import list_staged_records, stage_capture


def _row(record_id, field, value):
    return EvidenceRow(
        record_id=record_id, field=field, value=value,
        source_uri="https://example.com/p", method="scrape", confidence=0.9,
    )


def test_stage_capture_writes_evidence_and_images_immediately(tmp_path):
    rows = [_row("P1", "Material", "Aluminum"), _row("P1", "Color", "Silver")]
    images = [b"\x89PNG-fake-bytes-1", b"\x89PNG-fake-bytes-2"]

    record_dir = stage_capture("job-a", "P1", rows, images, staging_root=tmp_path)

    assert record_dir == tmp_path / "job-a" / "P1"
    evidence_path = record_dir / "evidence.jsonl"
    assert evidence_path.exists()
    lines = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
    assert {(row["field"], row["value"]) for row in lines} == {
        ("Material", "Aluminum"), ("Color", "Silver"),
    }
    assert (record_dir / "image_0.raw").read_bytes() == images[0]
    assert (record_dir / "image_1.raw").read_bytes() == images[1]
    # No ZIP has been built yet -- staging is a separate, earlier step.
    assert not any(p.suffix == ".zip" for p in tmp_path.rglob("*"))


def test_stage_capture_with_no_images_writes_evidence_only(tmp_path):
    rows = [_row("P2", "Brand", "TBK Metal")]
    record_dir = stage_capture("job-a", "P2", rows, [], staging_root=tmp_path)

    assert (record_dir / "evidence.jsonl").exists()
    assert not list(record_dir.glob("image_*.raw"))


def test_list_staged_records_reflects_whats_on_disk(tmp_path):
    stage_capture("job-b", "P3", [_row("P3", "Brand", "X")], [], staging_root=tmp_path)
    stage_capture("job-b", "P1", [_row("P1", "Brand", "Y")], [], staging_root=tmp_path)
    stage_capture("job-b", "P2", [_row("P2", "Brand", "Z")], [], staging_root=tmp_path)
    # A different job's records must not leak in.
    stage_capture("job-other", "P9", [_row("P9", "Brand", "W")], [], staging_root=tmp_path)

    assert list_staged_records("job-b", staging_root=tmp_path) == ["P1", "P2", "P3"]


def test_list_staged_records_for_unknown_job_is_empty_not_an_error(tmp_path):
    assert list_staged_records("never-staged", staging_root=tmp_path) == []
