"""Assembly tests: extracted pages -> EvidenceRow -> BK-PACK.

The pack must pass packages/bkpack's validator, every row must be sourced to a
pdf:// URI, a clean page yields a text row, and a garbled page yields no text
row (but keeps its images and is reported for OCR).
"""

from bkpack.validator import validate_bkpack
from pdfworker.assemble import build_pack_from_pdf
from pdfworker.extract import extract_text_and_images


def test_clean_pack_has_text_and_image_rows_and_validates(clean_pdf, tmp_path):
    pages = extract_text_and_images(clean_pdf)
    out = tmp_path / "clean.bkpack.zip"

    result = build_pack_from_pdf(pages, "clean.pdf", str(out))

    assert out.exists()
    assert validate_bkpack(str(out)).ok
    assert result.needs_ocr == []
    fields = {r.field for r in result.rows}
    assert "text" in fields
    assert any(f.startswith("image_") for f in fields)
    assert all(r.source_uri == "pdf://clean.pdf#page=1" for r in result.rows)
    assert all(r.method == "pdf" for r in result.rows)


def test_garbled_page_yields_no_text_row_but_keeps_images(garbled_pdf, tmp_path):
    pages = extract_text_and_images(garbled_pdf)
    out = tmp_path / "garbled.bkpack.zip"

    result = build_pack_from_pdf(pages, "garbled.pdf", str(out))

    assert result.needs_ocr == [1]
    fields = [r.field for r in result.rows]
    assert "text" not in fields  # untrusted text is never asserted
    assert any(f.startswith("image_") for f in fields)  # images still captured
    assert validate_bkpack(str(out)).ok
    assert all(r.source_uri == "pdf://garbled.pdf#page=1" for r in result.rows)
