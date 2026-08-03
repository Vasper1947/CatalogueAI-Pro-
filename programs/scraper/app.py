"""Program 1 scraper — HTTP surface.

    POST /scrape {"url": ...}   start a scrape job, returns a job id.
    GET  /scrape/{job_id}       job status and, when done, the result.

The job runs in a background thread (Playwright's sync API cannot run inside the
event loop). Job state is in-memory, which is fine for this scaffolding slice.
robots.txt is checked first; a disallowed URL is refused and never fetched.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from scraper.assemble import build_pack_from_fields
from scraper.discover import extract_structured_data, robots_allows

app = FastAPI(title="BK Foundry — Program 1 (scraper)")

_JOBS: dict[str, dict] = {}


class ScrapeRequest(BaseModel):
    url: str


def _run_job(job_id: str, url: str) -> None:
    job = _JOBS[job_id]
    try:
        if not robots_allows(url):
            job.update(status="refused", reason="disallowed by robots.txt")
            return
        fields = extract_structured_data(url)
        if not fields:
            job.update(
                status="done",
                fields={},
                evidence=[],
                bkpack=None,
                note="no schema.org/Product structured data found",
            )
            return
        out = Path(tempfile.gettempdir()) / f"bkpack-{job_id}.zip"
        rows = build_pack_from_fields(fields, url, str(out))
        job.update(
            status="done",
            fields=fields,
            evidence=[r.to_dict() for r in rows],
            bkpack=str(out),
        )
    except Exception as exc:  # noqa: BLE001
        # Job-runner boundary: record any failure in the job record rather than
        # letting it crash the background worker thread silently.
        job.update(status="error", error=str(exc))


@app.post("/scrape")
def start_scrape(req: ScrapeRequest, background: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {"status": "queued", "url": req.url}
    background.add_task(_run_job, job_id, req.url)
    return {"job_id": job_id, "status": "queued"}


@app.get("/scrape/{job_id}")
def get_scrape(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}
    return {"job_id": job_id, **job}
