"""write_sku_csv: one row per staged record, columns = the union of fields
actually present, values pulled directly from staged evidence -- never a
separate source, never guessed. A missing field is a blank cell.
"""

import csv
import io

from bkpack.evidence import EvidenceRow
from export.csv_export import write_sku_csv
from export.staging import stage_capture


def _row(record_id, field, value):
    return EvidenceRow(
        record_id=record_id, field=field, value=value,
        source_uri="https://example.com/p", method="scrape", confidence=0.9,
    )


def _parsed_rows(csv_text):
    return list(csv.DictReader(io.StringIO(csv_text)))


def test_csv_columns_are_the_union_of_fields_actually_present(tmp_path):
    stage_capture(
        "job-c", "P1",
        [_row("P1", "Material", "Aluminum"), _row("P1", "Color", "Silver")],
        [], staging_root=tmp_path,
    )
    stage_capture(
        "job-c", "P2",
        [_row("P2", "Material", "Steel"), _row("P2", "Length", "2.5 m")],
        [], staging_root=tmp_path,
    )

    csv_text = write_sku_csv("job-c", staging_root=tmp_path)
    rows = _parsed_rows(csv_text)

    header = set(rows[0].keys())
    assert header == {"record_id", "Material", "Color", "Length", "images"}
    by_id = {r["record_id"]: r for r in rows}
    assert by_id["P1"]["Material"] == "Aluminum"
    assert by_id["P1"]["Color"] == "Silver"
    # Length is absent for P1 -- a genuinely blank cell, never fabricated.
    assert by_id["P1"]["Length"] == ""
    assert by_id["P2"]["Material"] == "Steel"
    assert by_id["P2"]["Length"] == "2.5 m"
    assert by_id["P2"]["Color"] == ""


def test_csv_never_fabricates_a_field_present_only_elsewhere(tmp_path):
    stage_capture("job-d", "P1", [_row("P1", "Brand", "Bosch")], [], staging_root=tmp_path)
    stage_capture("job-d", "P2", [_row("P2", "Grade", "Fe500")], [], staging_root=tmp_path)

    rows = _parsed_rows(write_sku_csv("job-d", staging_root=tmp_path))
    by_id = {r["record_id"]: r for r in rows}

    assert by_id["P1"]["Grade"] == ""
    assert by_id["P2"]["Brand"] == ""


def test_csv_images_column_lists_processed_webp_filenames(tmp_path):
    record_dir = stage_capture(
        "job-e", "P1", [_row("P1", "Brand", "TBK")], [], staging_root=tmp_path
    )
    # Simulate that image processing (Task 2) has already produced webp files
    # in this record's staging directory, as finalize_zip ensures before
    # calling write_sku_csv.
    (record_dir / "P1_0.webp").write_bytes(b"fake-webp-bytes")
    (record_dir / "P1_1.webp").write_bytes(b"fake-webp-bytes")

    rows = _parsed_rows(write_sku_csv("job-e", staging_root=tmp_path))
    assert rows[0]["images"] == "P1_0.webp; P1_1.webp"


def test_csv_images_column_blank_when_no_images_processed(tmp_path):
    stage_capture("job-f", "P1", [_row("P1", "Brand", "TBK")], [], staging_root=tmp_path)

    rows = _parsed_rows(write_sku_csv("job-f", staging_root=tmp_path))
    assert rows[0]["images"] == ""
