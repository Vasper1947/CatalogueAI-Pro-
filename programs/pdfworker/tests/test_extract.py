"""Extraction tests against real, built-at-test-time PDFs."""

from pdfworker.extract import extract_text_and_images


def test_clean_pdf_extracts_text_and_keeps_only_large_image(clean_pdf):
    pages = extract_text_and_images(clean_pdf)

    assert len(pages) == 1
    page = pages[0]
    assert page.page_number == 1
    assert "Aluminum Tile Trim" in page.text
    assert page.garbled is False
    # The 16x16 logo is skipped; only the 200x200 image is kept.
    assert len(page.images) == 1
    assert page.images[0].width >= 64
    assert page.images[0].height >= 64
    assert page.images[0].data


def test_min_image_dim_threshold_is_configurable(clean_pdf):
    pages = extract_text_and_images(clean_pdf, min_image_dim=8)
    # With a lower threshold, the tiny image is included too.
    assert len(pages[0].images) == 2
