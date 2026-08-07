"""Assembly-layer tests: discovered fields -> EvidenceRow list -> BK-PACK.

The pack must pass packages/bkpack's own validator, every row must carry a real
source_uri, and a page with no fields must produce no pack (never an empty or
fabricated one).
"""

from bkpack.validator import validate_bkpack
from export.staging import list_staged_records, load_staged_evidence_rows
from scraper.assemble import build_pack_from_fields, to_evidence_rows


def test_rows_carry_real_source_uri_and_invent_nothing():
    fields = {"name": "Trim", "sku": "S1", "price": "2.35"}
    url = "https://example.com/products/trim"

    rows = to_evidence_rows(fields, url)

    assert {r.field for r in rows} == {"name", "sku", "price"}
    assert all(r.source_uri == url for r in rows)
    assert all(r.method == "scrape" for r in rows)
    # Exactly the fields we passed in — no extra invented rows.
    assert len(rows) == 3


def test_assembled_pack_passes_validate_bkpack(tmp_path):
    fields = {
        "name": "Aluminum Tile Trim 10mm Silver",
        "sku": "ATT-10-SIL",
        "image": "https://example.com/img/att-10-sil.jpg",
        "brand": "Foshan Guanghong",
        "price": "2.35",
    }
    url = "https://example.com/products/att-10-sil"
    out = tmp_path / "out.bkpack.zip"

    rows = build_pack_from_fields(fields, url, str(out))

    assert out.exists()
    report = validate_bkpack(str(out))
    assert report.ok, report.errors
    assert rows and all(r.source_uri == url for r in rows)


def test_no_fields_builds_no_pack(tmp_path):
    out = tmp_path / "none.bkpack.zip"
    rows = build_pack_from_fields({}, "https://example.com/products/x", str(out))
    assert rows == []
    assert not out.exists()


def test_job_id_stages_the_capture_before_building_the_pack(tmp_path):
    fields = {"name": "Aluminum Tile Trim 10mm Silver", "sku": "ATT-10-SIL", "price": "2.35"}
    url = "https://example.com/products/att-10-sil"
    out = tmp_path / "out.bkpack.zip"
    staging_root = tmp_path / "staging"

    rows = build_pack_from_fields(
        fields, url, str(out), job_id="scrape-run-1", staging_root=staging_root
    )

    assert list_staged_records("scrape-run-1", staging_root=staging_root) == ["ATT-10-SIL"]
    staged_rows = load_staged_evidence_rows(
        "scrape-run-1", "ATT-10-SIL", staging_root=staging_root
    )
    assert {(r.field, r.value) for r in staged_rows} == {(r.field, r.value) for r in rows}


def test_omitting_job_id_stages_nothing_fully_backward_compatible(tmp_path):
    fields = {"name": "Trim", "sku": "S1", "price": "2.35"}
    out = tmp_path / "out.bkpack.zip"
    staging_root = tmp_path / "staging"

    build_pack_from_fields(fields, "https://example.com/products/trim", str(out))

    assert not staging_root.exists()  # no job_id -> staging never touched
