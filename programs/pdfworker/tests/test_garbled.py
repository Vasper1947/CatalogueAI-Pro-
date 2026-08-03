"""Garbled-detection tests: pure helpers on strings + real pages."""

import fitz
from pdfworker.garbled import has_cid_tokens, is_page_garbled, replacement_ratio


def test_replacement_ratio_counts_fffd():
    assert replacement_ratio("") == 0.0
    assert replacement_ratio("abc") == 0.0
    assert replacement_ratio("��ab") == 0.5


def test_has_cid_tokens_detects_unmapped_glyph_tokens():
    assert has_cid_tokens("(cid:3)(cid:12) text") is True
    assert has_cid_tokens("normal text with (parentheses)") is False


def test_clean_page_is_not_flagged(clean_pdf):
    with fitz.open(clean_pdf) as doc:
        assert is_page_garbled(doc.load_page(0)) is False


def test_garbled_page_is_flagged(garbled_pdf):
    with fitz.open(garbled_pdf) as doc:
        assert is_page_garbled(doc.load_page(0)) is True
