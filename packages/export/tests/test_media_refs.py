"""media_refs (discovered video/gif URL metadata) staged alongside evidence,
aggregated into finalize_zip's output -- same "included in finalize_zip's
output" requirement as SKU.csv, omitted entirely (not an empty file) when no
record has any.
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


def test_media_refs_staged_immediately_to_disk(tmp_path):
    refs = [{"url": "https://example.com/demo.mp4", "media_type": "video"}]
    record_dir = stage_capture(
        "job-j", "P1", [_row("P1", "Brand", "X")], [],
        staging_root=tmp_path, media_refs=refs,
    )
    staged = json.loads((record_dir / "media_refs.json").read_text(encoding="utf-8"))
    assert staged == refs


def test_no_media_refs_writes_no_file(tmp_path):
    record_dir = stage_capture(
        "job-k", "P1", [_row("P1", "Brand", "X")], [], staging_root=tmp_path,
    )
    assert not (record_dir / "media_refs.json").exists()


def test_finalize_zip_aggregates_media_refs_across_records(tmp_path):
    stage_capture(
        "job-l", "P1", [_row("P1", "Brand", "X")], [], staging_root=tmp_path,
        media_refs=[{"url": "https://example.com/a.gif", "media_type": "gif"}],
    )
    stage_capture(
        "job-l", "P2", [_row("P2", "Brand", "Y")], [], staging_root=tmp_path,
        media_refs=[{"url": "https://example.com/b.mp4", "media_type": "video"}],
    )
    out = tmp_path / "out.zip"
    finalize_zip("job-l", str(out), staging_root=tmp_path, producer=PRODUCER)

    with zipfile.ZipFile(out) as zf:
        assert "media_refs.json" in zf.namelist()
        refs = json.loads(zf.read("media_refs.json").decode("utf-8"))
    assert refs == {
        "P1": [{"url": "https://example.com/a.gif", "media_type": "gif"}],
        "P2": [{"url": "https://example.com/b.mp4", "media_type": "video"}],
    }


def test_finalize_zip_omits_media_refs_file_when_none_staged(tmp_path):
    stage_capture("job-m", "P1", [_row("P1", "Brand", "X")], [], staging_root=tmp_path)
    out = tmp_path / "out.zip"
    finalize_zip("job-m", str(out), staging_root=tmp_path, producer=PRODUCER)

    with zipfile.ZipFile(out) as zf:
        assert "media_refs.json" not in zf.namelist()  # never an empty/fabricated file
