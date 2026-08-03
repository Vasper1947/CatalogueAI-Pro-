"""Garbled-font DETECTION only for PDF pages — flag, never fix.

A page's extracted text is untrustworthy when glyphs are not mapped back to
characters. We detect that from three signals:
  * a high ratio of U+FFFD replacement characters,
  * (cid:N) tokens standing in for unmapped glyphs, and
  * embedded fonts with no /ToUnicode map on a page whose text won't extract.

Recovering the real text (OCR) is explicitly NOT part of this slice.
"""

from __future__ import annotations

import re

import fitz

CID_TOKEN = re.compile(r"\(cid:\d+\)")
FFFD = "�"
DEFAULT_FFFD_THRESHOLD = 0.02


def replacement_ratio(text: str) -> float:
    """Fraction of characters in ``text`` that are U+FFFD replacement chars."""
    if not text:
        return 0.0
    return text.count(FFFD) / len(text)


def has_cid_tokens(text: str) -> bool:
    """True if the text contains (cid:N) tokens left by unmapped glyphs."""
    return CID_TOKEN.search(text) is not None


def fonts_missing_tounicode(page: fitz.Page) -> list[str]:
    """Base font names of embedded fonts on the page that lack a /ToUnicode map."""
    doc = page.parent
    missing: list[str] = []
    for info in page.get_fonts(full=True):
        xref = info[0]
        basefont = info[3] if len(info) > 3 else ""
        try:
            key_type, _ = doc.xref_get_key(xref, "ToUnicode")
        except (ValueError, RuntimeError):
            key_type = "null"
        if key_type == "null":
            missing.append(basefont)
    return missing


def _looks_unextractable(text: str) -> bool:
    """True if the page yielded almost no real word characters."""
    stripped = text.strip()
    if not stripped:
        return True
    word_chars = sum(1 for ch in stripped if ch.isalnum())
    return word_chars / len(stripped) < 0.2


def is_page_garbled(
    page: fitz.Page, *, fffd_threshold: float = DEFAULT_FFFD_THRESHOLD
) -> bool:
    """True if the page's extracted text cannot be trusted.

    Strong signals (either one alone flags): a high U+FFFD ratio, or (cid:N)
    tokens. Missing /ToUnicode on its own does NOT flag — plenty of clean
    base-14 fonts lack it — it only flags when combined with text that will not
    extract into real words.
    """
    text = page.get_text()
    if has_cid_tokens(text):
        return True
    if replacement_ratio(text) > fffd_threshold:
        return True
    return bool(fonts_missing_tounicode(page)) and _looks_unextractable(text)
