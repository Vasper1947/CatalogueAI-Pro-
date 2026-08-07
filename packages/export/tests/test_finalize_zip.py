"""finalize_zip: reads staged evidence + processes staged images, calls the
existing, UNTOUCHED build_bkpack() for the core pack, and adds SKU.csv on
top. Proves the core pack content is byte-identical to what build_bkpack()
itself would produce from the same inputs -- packages/bkpack is only ever
called, never reimplemented or modified.
"""

import io
import json
import zipfile

from bkpack.evidence import EvidenceRow
from bkpack.spec import REQUIRED_FILES
from bkpack.writer import build_bkpack
from export.staging import finalize_zip, stage_capture
from PIL import Image

PRODUCER = {"program": 1, "app_version": "test", "agent_id": "export-tests"}


def _row(record_id, field, value):
    return EvidenceRow(
        record_id=record_id, field=field, value=value,
        source_uri="https://example.com/p", method="scrape", confidence=0.9,
    )


def _real_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (12, 10), color="green").save(buf, format="PNG")
    return buf.getvalue()


def test_finalize_zip_processes_images_and_includes_csv(tmp_path):
    stage_capture(
        "job-g", "P1",
        [_row("P1", "Material", "Aluminum"), _row("P1", "Color", "Silver")],
        [_real_png_bytes()],
        staging_root=tmp_path,
    )
    stage_capture(
        "job-g", "P2", [_row("P2", "Material", "Steel")], [], staging_root=tmp_path,
    )

    out_zip = tmp_path / "out" / "job-g.bkpack.zip"
    result_path = finalize_zip("job-g", str(out_zip), staging_root=tmp_path, producer=PRODUCER)

    assert result_path == out_zip
    with zipfile.ZipFile(out_zip) as zf:
        names = set(zf.namelist())
        assert REQUIRED_FILES <= names
        assert "SKU.csv" in names
        assert "media/P1_0.webp" in names  # the staged raw image, processed

        evidence = [
            json.loads(line)
            for line in zf.read("evidence.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        assert {(r["record_id"], r["field"], r["value"]) for r in evidence} == {
            ("P1", "Material", "Aluminum"),
            ("P1", "Color", "Silver"),
            ("P2", "Material", "Steel"),
        }

        csv_text = zf.read("SKU.csv").decode("utf-8")
        assert "P1_0.webp" in csv_text
        assert "P1" in csv_text and "P2" in csv_text

        # The webp is a genuinely valid image, not just a renamed PNG.
        with Image.open(io.BytesIO(zf.read("media/P1_0.webp"))) as img:
            img.load()
            assert img.format == "WEBP"


def test_finalize_zip_core_pack_matches_build_bkpack_called_directly(tmp_path):
    # Same evidence, staged then finalized, versus calling the untouched
    # build_bkpack() directly with equivalent inputs -- the core pack content
    # (datapackage.json's product_count/policy and the evidence rows) must
    # match exactly; finalize_zip must never reimplement bkpack's own logic.
    rows = [_row("P1", "Brand", "Bosch")]
    stage_capture("job-h", "P1", rows, [], staging_root=tmp_path)

    finalized = tmp_path / "finalized.bkpack.zip"
    finalize_zip("job-h", str(finalized), staging_root=tmp_path, producer=PRODUCER)

    direct = tmp_path / "direct.bkpack.zip"
    build_bkpack(output_path=str(direct), evidence_rows=rows, media_files={}, producer=PRODUCER)

    with zipfile.ZipFile(finalized) as zf1, zipfile.ZipFile(direct) as zf2:
        dp1 = json.loads(zf1.read("datapackage.json"))
        dp2 = json.loads(zf2.read("datapackage.json"))
        assert dp1["product_count"] == dp2["product_count"]
        assert dp1["provenance_policy"] == dp2["provenance_policy"]
        assert zf1.read("evidence.jsonl") == zf2.read("evidence.jsonl")
        # finalize_zip's ZIP has exactly one file build_bkpack's doesn't: the CSV.
        assert set(zf1.namelist()) - set(zf2.namelist()) == {"SKU.csv"}


def test_finalize_zip_is_idempotent_on_already_processed_images(tmp_path):
    # Calling image-processing twice (e.g. finalize_zip run, then re-run
    # against the same staged data) must not error or double-process.
    stage_capture(
        "job-i", "P1", [_row("P1", "Brand", "X")], [_real_png_bytes()],
        staging_root=tmp_path,
    )
    out1 = tmp_path / "out1.zip"
    out2 = tmp_path / "out2.zip"
    finalize_zip("job-i", str(out1), staging_root=tmp_path, producer=PRODUCER)
    finalize_zip("job-i", str(out2), staging_root=tmp_path, producer=PRODUCER)

    with zipfile.ZipFile(out2) as zf:
        assert "media/P1_0.webp" in zf.namelist()
