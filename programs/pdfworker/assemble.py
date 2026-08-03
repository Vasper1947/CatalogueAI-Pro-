"""Assemble PDF extraction into a BK-PACK using packages/bkpack as-is.

Each page's trustworthy content becomes EvidenceRows sourced to
``pdf://<filename>#page=<n>``:
  * a clean page contributes one ``text`` row;
  * a garbled page contributes NO text row — we do not assert text we cannot
    trust — and is reported in ``needs_ocr`` instead;
  * embedded images become rows on any page (clean or garbled), since image
    existence is not affected by garbled fonts.

packages/bkpack is used exactly as it already exists — no changes to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack

CONFIDENCE_CLEAN = 0.9
MEDIA_DIR = "media"
PRODUCER = {"program": 4, "app_version": "0.1.0", "agent_id": "pdfworker"}


@dataclass
class AssembleResult:
    rows: list[EvidenceRow]
    needs_ocr: list[int]  # 1-based page numbers flagged garbled
    media_count: int


def _stem(filename: str) -> str:
    return Path(filename).stem or filename


def to_evidence_and_media(pages, filename: str):
    """Build ``(rows, media_files, needs_ocr)`` from extracted pages.

    ``pages`` is a list of pdfworker.extract.PageContent. Nothing is invented:
    a page with no trustworthy text and no images produces no rows.
    """
    stem = _stem(filename)
    rows: list[EvidenceRow] = []
    media: dict[str, bytes] = {}
    needs_ocr: list[int] = []

    for page in pages:
        record_id = f"{stem}-p{page.page_number}"
        source_uri = f"pdf://{filename}#page={page.page_number}"

        if page.garbled:
            needs_ocr.append(page.page_number)
        elif page.text.strip():
            rows.append(
                EvidenceRow(
                    record_id=record_id,
                    field="text",
                    value=page.text.strip(),
                    source_uri=source_uri,
                    method="pdf",
                    confidence=CONFIDENCE_CLEAN,
                )
            )

        for image in page.images:
            media_name = f"{stem}_p{page.page_number}_img{image.index}.{image.ext}"
            media[media_name] = image.data
            rows.append(
                EvidenceRow(
                    record_id=record_id,
                    field=f"image_{image.index}",
                    value=f"{MEDIA_DIR}/{media_name}",
                    source_uri=source_uri,
                    method="pdf",
                    confidence=CONFIDENCE_CLEAN,
                )
            )

    return rows, media, needs_ocr


def build_pack_from_pdf(pages, filename: str, output_path: str) -> AssembleResult:
    """Build a BK-PACK at output_path from a PDF's extracted pages.

    Returns the rows written, the pages needing OCR, and the media count. If no
    trustworthy rows resulted, no pack is built (never an empty/fabricated one).
    """
    rows, media, needs_ocr = to_evidence_and_media(pages, filename)
    if not rows:
        return AssembleResult(rows=[], needs_ocr=needs_ocr, media_count=0)
    build_bkpack(
        output_path=output_path,
        evidence_rows=rows,
        media_files=media,
        producer=PRODUCER,
    )
    return AssembleResult(rows=rows, needs_ocr=needs_ocr, media_count=len(media))
