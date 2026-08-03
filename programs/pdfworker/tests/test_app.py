"""API-surface tests for the PDF worker.

These drive the job function directly against real fixture PDFs (no ASGI
TestClient / httpx) so no new dependency is needed. The extract + garbled +
assemble + BK-PACK path runs for real.
"""

from pdfworker.app import _JOBS, _run_job, get_pdf


def test_run_job_clean_pdf_completes_with_evidence(clean_pdf):
    _JOBS["clean-1"] = {"status": "queued", "filename": "clean.pdf"}

    _run_job("clean-1", clean_pdf, "clean.pdf")
    result = get_pdf("clean-1")

    assert result["status"] == "done"
    assert result["needs_ocr"] == []
    assert result["evidence"]
    assert any(row["field"] == "text" for row in result["evidence"])
    assert all(row["source_uri"].startswith("pdf://") for row in result["evidence"])


def test_run_job_garbled_pdf_marks_needs_ocr_and_omits_text(garbled_pdf):
    _JOBS["garbled-1"] = {"status": "queued", "filename": "garbled.pdf"}

    _run_job("garbled-1", garbled_pdf, "garbled.pdf")
    result = get_pdf("garbled-1")

    assert result["status"] == "done"
    assert result["needs_ocr"] == [1]
    assert all(row["field"] != "text" for row in result["evidence"])
