"""Shared fixtures: real PDFs built at test time with fitz.

The clean PDF has extractable text plus one large image (kept) and one tiny
image (skipped as a logo/icon). The garbled PDF carries (cid:N) tokens that
stand in for unmapped glyphs, so garbled detection fires — real garbled-font
examples are BK's private historical supplier PDFs, not something buildable
from public data, so we synthesise the signal for the test.
"""

import io
from pathlib import Path

import fitz
import pytest
from PIL import Image


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _build_clean(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Aluminum Tile Trim 10mm Silver\nSKU ATT-10-SIL\nPrice 2.35 USD",
        fontname="helv",
        fontsize=12,
    )
    page.insert_image(fitz.Rect(72, 110, 272, 310), stream=_png_bytes((200, 200), (180, 180, 180)))
    page.insert_image(fitz.Rect(72, 320, 92, 340), stream=_png_bytes((16, 16), (20, 20, 20)))
    doc.save(str(path))
    doc.close()


def _build_garbled(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "(cid:12)(cid:44)(cid:88) (cid:3)(cid:7) sample line",
        fontname="helv",
        fontsize=12,
    )
    page.insert_image(fitz.Rect(72, 110, 272, 310), stream=_png_bytes((200, 200), (120, 120, 120)))
    doc.save(str(path))
    doc.close()


@pytest.fixture
def clean_pdf(tmp_path) -> str:
    path = tmp_path / "clean.pdf"
    _build_clean(path)
    return str(path)


@pytest.fixture
def garbled_pdf(tmp_path) -> str:
    path = tmp_path / "garbled.pdf"
    _build_garbled(path)
    return str(path)
