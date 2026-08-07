"""The TBK Metal Edge Trim page, closing the loop from last round: the real
end-to-end proof that couldn't happen then, because build_pack_from_fields's
pre-existing gate (fixed in programs/scraper/assemble.py this round) returned
[] before ever reaching spec_table_rows for a page with no JSON-LD -- exactly
TBK's real shape. This is the same page used throughout this project's
detect/populate hardening arc.

The 8 (key, value) pairs and the product photo below are REAL -- live-
reconfirmed the day of this fix (identical across every capture this session).
tbk_real_product_image.jpg is the actual product photo fetched from this
page's own real image URL. Reproduced here as fixtures (HTML string + a
committed binary image file), not fetched live in this test, for the same
reason every other test in this suite avoids a live network dependency:
reproducible, fast, CI-safe.
"""

import json
import zipfile
from pathlib import Path

from export.staging import finalize_zip, list_staged_records
from scraper.assemble import build_pack_from_fields

TBK_URL = "https://www.tbkmetal.com/products/aluminium-bullnose-border-tile-edge-trim/"

_TBK_HTML = """
<html><body>
<table>
  <tr><td>Material:</td><td>Aluminum Alloy</td></tr>
  <tr><td>Finish:</td><td>BA/Matte/Brush/Satin/Mirror/Emboss</td></tr>
  <tr><td>Color:</td><td>Silver/Golden/Bronze/Black Titanium/Rose Gold/Champagne, etc.</td></tr>
  <tr><td>Height:</td><td>8/10/12mm / Customized.</td></tr>
</table>
<table>
  <tr><td>Thickness:</td><td>0.5-2.0 mm / Customizable</td></tr>
  <tr><td>Length:</td><td>2.4/2.5/2.7/3 Meters</td></tr>
  <tr><td>Packing:</td><td>Plastic film for each piece, outside with carton</td></tr>
  <tr><td>Applications:</td><td>Ceramic tile edge protection &amp; decoration</td></tr>
</table>
</body></html>
"""

_FIXTURE_IMAGE = Path(__file__).parent / "fixtures" / "tbk_real_product_image.jpg"
PRODUCER = {"program": 1, "app_version": "0.1.0", "agent_id": "scraper"}


def test_tbk_page_with_no_json_ld_now_stages_its_real_spec_table_data(tmp_path):
    # TBK's page genuinely has NO Product-typed JSON-LD (live-reconfirmed) --
    # fields={} is the honest, real shape, not a stand-in for something else.
    staging_root = tmp_path / "staging"
    job_id = "tbk-real-page-integration"
    real_image_bytes = _FIXTURE_IMAGE.read_bytes()

    rows = build_pack_from_fields(
        {}, TBK_URL, str(tmp_path / "unused_inline_pack.bkpack.zip"),
        page_html=_TBK_HTML,
        job_id=job_id,
        staging_root=staging_root,
        image_bytes_list=[real_image_bytes],
    )
    # Before the fix: 0 rows (the gate returned [] before spec_table_rows ever
    # ran). Now: exactly the page's 8 real spec-table values.
    assert len(rows) == 8
    assert {r.field for r in rows} == {
        "Material", "Finish", "Color", "Height",
        "Thickness", "Length", "Packing", "Applications",
    }

    record_id = "aluminium-bullnose-border-tile-edge-trim"  # URL-slug fallback (no sku)
    assert list_staged_records(job_id, staging_root=staging_root) == [record_id]
    record_dir = staging_root / job_id / record_id
    assert (record_dir / "evidence.jsonl").exists()
    assert (record_dir / "image_0.raw").read_bytes() == real_image_bytes

    output_zip = tmp_path / "tbk.bkpack.zip"
    result = finalize_zip(job_id, str(output_zip), staging_root=staging_root, producer=PRODUCER)
    assert result == output_zip

    with zipfile.ZipFile(output_zip) as zf:
        names = set(zf.namelist())
        assert {"datapackage.json", "evidence.jsonl", "manifest-sha256.txt", "SKU.csv"} <= names
        assert f"media/{record_id}_0.webp" in names

        evidence = [
            json.loads(line)
            for line in zf.read("evidence.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        by_field = {r["field"]: r["value"] for r in evidence}
        assert by_field["Material"] == "Aluminum Alloy"
        assert by_field["Height"] == "8/10/12mm / Customized."
        assert by_field["Length"] == "2.4/2.5/2.7/3 Meters"

        csv_text = zf.read("SKU.csv").decode("utf-8")
        assert record_id in csv_text
        assert f"{record_id}_0.webp" in csv_text
        assert "Aluminum Alloy" in csv_text

        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(zf.read(f"media/{record_id}_0.webp"))) as img:
            img.load()
            assert img.format == "WEBP"
            assert img.size == (800, 533)  # the real product photo's dimensions
