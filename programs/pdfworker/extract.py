"""Extract text and embedded images from a born-digital PDF (PyMuPDF / fitz).

This slice handles normal, non-garbled PDFs. Each page's text is paired with a
garbled flag (from garbled.py) so downstream assembly knows whether the text can
be trusted. Recovering garbled text (OCR) is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import fitz

from pdfworker.garbled import is_page_garbled

MIN_IMAGE_DIM = 64  # px — below this an image is treated as a logo/icon and skipped


@dataclass
class PageImage:
    index: int
    ext: str
    width: int
    height: int
    data: bytes


@dataclass
class PageContent:
    page_number: int  # 1-based
    text: str
    garbled: bool = False
    images: list[PageImage] = field(default_factory=list)


def extract_text_and_images(
    pdf_path: str, *, min_image_dim: int = MIN_IMAGE_DIM
) -> list[PageContent]:
    """Return per-page text, garbled flag, and embedded images for a PDF.

    Images whose stored width or height is below ``min_image_dim`` are skipped
    (logos/icons). The same image referenced twice on a page is emitted once.
    Page numbers are 1-based.
    """
    pages: list[PageContent] = []
    with fitz.open(pdf_path) as doc:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            images: list[PageImage] = []
            seen_xrefs: set[int] = set()
            for info in page.get_images(full=True):
                xref = info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                extracted = doc.extract_image(xref)
                if not extracted:
                    continue
                width = extracted.get("width", 0)
                height = extracted.get("height", 0)
                if width < min_image_dim or height < min_image_dim:
                    continue
                images.append(
                    PageImage(
                        index=len(images),
                        ext=extracted.get("ext", "png"),
                        width=width,
                        height=height,
                        data=extracted["image"],
                    )
                )
            pages.append(
                PageContent(
                    page_number=page_index + 1,
                    text=page.get_text(),
                    garbled=is_page_garbled(page),
                    images=images,
                )
            )
    return pages
