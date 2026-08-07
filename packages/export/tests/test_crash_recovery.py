"""Proves the actual crash-recovery claim (Task 1's real point) -- not just
that staging and finalizing happen to work when called back to back, but
that finalize_zip needs NOTHING beyond job_id + staging_root to fully
reconstruct a complete, correct pack. That is what "no data lost ever" means:
a process that died right after stage_capture() calls has lost nothing --
anyone, later, on a fresh call, can finish the job.
"""

import json
import zipfile

from bkpack.evidence import EvidenceRow
from export.staging import finalize_zip, stage_capture

PRODUCER = {"program": 1, "app_version": "test", "agent_id": "export-tests"}


def _row(record_id, field, value):
    return EvidenceRow(
        record_id=record_id, field=field, value=value,
        source_uri="https://example.com/p", method="scrape", confidence=0.9,
    )


def _run_1_stage_several_captures_then_the_process_ends(job_id, staging_root):
    """Simulates a scrape run that stages several captures and then dies --
    it stages, and returns nothing usable to any later step. No Python-level
    reference to what it staged survives past this function."""
    stage_capture(
        job_id, "P1",
        [_row("P1", "Material", "Aluminum"), _row("P1", "Color", "Silver")],
        [], staging_root=staging_root,
    )
    stage_capture(
        job_id, "P2",
        [_row("P2", "Material", "Steel"), _row("P2", "Grade", "Fe500")],
        [], staging_root=staging_root,
    )
    stage_capture(
        job_id, "P3", [_row("P3", "Brand", "TBK Metal")], [], staging_root=staging_root,
    )
    # Deliberately return nothing -- run 2 must not receive rows/values, only
    # the job_id, exactly like a genuinely separate, later process would.


def _run_2_resumes_and_finalizes_independently(job_id, staging_root, output_path):
    """A completely independent call, receiving ONLY job_id and staging_root
    -- as if it were a different process, run much later, that never saw
    run 1's in-memory state at all."""
    return finalize_zip(job_id, str(output_path), staging_root=staging_root, producer=PRODUCER)


def test_every_staged_capture_survives_a_stage_then_finalize_process_boundary(tmp_path):
    job_id = "crash-recovery-job"
    staging_root = tmp_path / "staging"

    # Run 1: stage, then "the process ends" -- nothing carried forward.
    _run_1_stage_several_captures_then_the_process_ends(job_id, staging_root)

    # Run 2: a genuinely separate call, resuming from disk alone.
    output_path = tmp_path / "recovered.bkpack.zip"
    result = _run_2_resumes_and_finalizes_independently(job_id, staging_root, output_path)

    assert result == output_path
    with zipfile.ZipFile(output_path) as zf:
        evidence = [
            json.loads(line)
            for line in zf.read("evidence.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
    by_record = {}
    for row in evidence:
        by_record.setdefault(row["record_id"], {})[row["field"]] = row["value"]

    # Every single field staged in run 1 -- across all three records --
    # actually made it into the final ZIP. Nothing lost.
    assert by_record == {
        "P1": {"Material": "Aluminum", "Color": "Silver"},
        "P2": {"Material": "Steel", "Grade": "Fe500"},
        "P3": {"Brand": "TBK Metal"},
    }


def test_finalize_can_be_called_a_second_time_later_without_losing_or_duplicating_data(tmp_path):
    # A run that finalizes once, then (e.g. a retry, or a later re-export
    # request) finalizes again from the SAME staged data, must get the same
    # complete result both times -- staging is never consumed/destroyed by
    # finalizing.
    job_id = "resumable-twice"
    staging_root = tmp_path / "staging"
    stage_capture(job_id, "P1", [_row("P1", "Brand", "X")], [], staging_root=staging_root)

    first = finalize_zip(job_id, str(tmp_path / "first.zip"), staging_root=staging_root, producer=PRODUCER)
    second = finalize_zip(job_id, str(tmp_path / "second.zip"), staging_root=staging_root, producer=PRODUCER)

    with zipfile.ZipFile(first) as zf1, zipfile.ZipFile(second) as zf2:
        assert zf1.read("evidence.jsonl") == zf2.read("evidence.jsonl")
