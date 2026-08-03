"""Program 4 PDF worker — HTTP surface.

    POST /pdf  (multipart file)  start a job, returns a job id.
    GET  /pdf/{job_id}           status + needs_ocr + evidence + bkpack path.

The job runs in a background thread; job state is in-memory, which is fine for
this scaffolding slice.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, UploadFile

from pdfworker.assemble import build_pack_from_pdf
from pdfworker.extract import extract_text_and_images

app = FastAPI(title="BK Foundry — Program 4 (PDF worker)")

_JOBS: dict[str, dict] = {}


def _run_job(job_id: str, pdf_path: str, filename: str) -> None:
    job = _JOBS[job_id]
    try:
        pages = extract_text_and_images(pdf_path)
        out = Path(tempfile.gettempdir()) / f"pdfpack-{job_id}.zip"
        result = build_pack_from_pdf(pages, filename, str(out))
        job.update(
            status="done",
            pages=len(pages),
            needs_ocr=result.needs_ocr,
            evidence=[r.to_dict() for r in result.rows],
            bkpack=str(out) if result.rows else None,
        )
    except Exception as exc:  # noqa: BLE001
        # Job-runner boundary: record any failure rather than crash the worker.
        job.update(status="error", error=str(exc))


@app.post("/pdf")
async def start_pdf(
    background: BackgroundTasks, file: Annotated[UploadFile, File()]
) -> dict:
    job_id = uuid.uuid4().hex
    data = await file.read()
    tmp = Path(tempfile.gettempdir()) / f"pdfin-{job_id}.pdf"
    tmp.write_bytes(data)
    _JOBS[job_id] = {"status": "queued", "filename": file.filename}
    background.add_task(_run_job, job_id, str(tmp), file.filename or "upload.pdf")
    return {"job_id": job_id, "status": "queued"}


@app.get("/pdf/{job_id}")
def get_pdf(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}
    return {"job_id": job_id, **job}
