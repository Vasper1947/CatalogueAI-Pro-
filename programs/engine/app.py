"""Program 3 engine — HTTP surface.

    POST /ingest {"bkpack_path": ...}   detect template + populate, returns job id.
    GET  /engine/{job_id}               detection + population + the Floor Price gate.

Every job result carries the fixed Floor Price notice: it is a manual step and
"ready_for_review" is NOT the same state as upload-ready. Job runs in a
background thread; state is in-memory (scaffolding slice).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from bkpack.reader import read_bkpack
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel
from schemas.store import DATA_DIR

from engine.detect import MATCH_THRESHOLD, match_template
from engine.populate import populate_from_evidence

app = FastAPI(title="BK Foundry — Program 3 (engine)")

_JOBS: dict[str, dict] = {}
_SCHEMA_CACHE: list = []
TOP_CANDIDATES = 8

# Fixed gate: Floor Price is never populated by the engine, and a
# ready_for_review population is NOT the same thing as upload-ready.
FLOOR_PRICE_NOTICE = {
    "field": "Floor Price",
    "status": "pending_manual",
    "reason": (
        "Floor Price is a business pricing decision set manually by BK management "
        "before upload. It has no source in scraped or extracted product data and "
        "is absent from all 510 templates, so the engine never populates it. "
        "'ready_for_review' means extracted fields are populated for review; it is "
        "NOT 'upload-ready' — Floor Price must still be set manually first."
    ),
}
_READINESS_NOTE = (
    "ready_for_review != upload-ready; the Floor Price manual step is a separate "
    "gate (see floor_price)."
)


class IngestRequest(BaseModel):
    bkpack_path: str


def load_schemas(data_dir: Path = DATA_DIR, *, force: bool = False) -> list:
    """Load parsed schemas from the store (cached). Missing store -> []."""
    if _SCHEMA_CACHE and not force:
        return _SCHEMA_CACHE
    _SCHEMA_CACHE.clear()
    for path in Path(data_dir).rglob("*.json"):
        if path.name == "index.json":
            continue
        try:
            _SCHEMA_CACHE.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return _SCHEMA_CACHE


def _candidate_dicts(candidates) -> list:
    return [
        {
            "category_path": c.category_path,
            "score": round(c.score, 3),
            "matched_fields": c.matched_fields,
        }
        for c in candidates[:TOP_CANDIDATES]
    ]


def _run_job(job_id: str, bkpack_path: str) -> None:
    job = _JOBS[job_id]
    # Set the fixed gate first, so even an error path carries it.
    job["floor_price"] = FLOOR_PRICE_NOTICE
    job["note"] = _READINESS_NOTE
    try:
        data = read_bkpack(bkpack_path)
        evidence = data["evidence"]
        schemas = load_schemas()
        best, confidence, candidates = match_template(evidence, schemas)
        job["evidence_fields"] = sorted({r["field"] for r in evidence if r.get("field")})
        job["schemas_available"] = len(schemas)
        job["detection"] = {
            "confidence": round(confidence, 3),
            "threshold": MATCH_THRESHOLD,
            "matched": None if best is None else best.get("category_path"),
            "top_candidates": _candidate_dicts(candidates),
        }
        if best is None:
            job["status"] = "no_template_match"
            job["population"] = None
        else:
            job["status"] = "template_matched"
            job["population"] = asdict(populate_from_evidence(evidence, best))
    except Exception as exc:  # noqa: BLE001
        # Job-runner boundary: record any failure rather than crash the worker.
        job["status"] = "error"
        job["error"] = str(exc)


@app.post("/ingest")
def start_ingest(req: IngestRequest, background: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {
        "status": "queued",
        "bkpack_path": req.bkpack_path,
        "floor_price": FLOOR_PRICE_NOTICE,
    }
    background.add_task(_run_job, job_id, req.bkpack_path)
    return {"job_id": job_id, "status": "queued", "floor_price": FLOOR_PRICE_NOTICE}


@app.get("/engine/{job_id}")
def get_engine(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id, "floor_price": FLOOR_PRICE_NOTICE}
    return {"job_id": job_id, **job}
