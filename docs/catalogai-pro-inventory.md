# CatalogAI Pro — scaffold inventory (pre-removal record)

This documents the `backend/`, `frontend/`, and `deployment/` trees and the old
`README.md` that shipped in commit `3ec4bae` ("Deploy: Complete CatalogAI Pro v3
frontend") **before they were removed**. It exists so the removal is a matter of
record, not a silent disappearance.

All findings below were read fresh from the git objects at `3ec4bae`
(`git show 3ec4bae:<path>`), not recalled from any earlier investigation.

**Verdict:** this is a non-functional scaffold / demo. Nothing in it extracts
real catalog data; several parts contradict each other. It is superseded by the
BK Foundry work (`packages/bkpack`, `packages/common`, `programs/`), which is
built on the "no evidence, no value" rule the scaffold violates. Removing it
loses no working capability.

## 1. `process_job()` is a hardcoded simulation, not extraction

`backend/backend/main.py` (the background worker, ~lines 331–362) does not read
the uploaded file at all. It loops `for i in range(1, 11)` and appends invented
products:

```python
# Simulate processing (replace with actual Claude extraction)
job.products_total = 10
...
    # Simulate extraction
    product = {
        "sku": f"PROD_{i:03d}",
        "name": f"Product {i}",
        "category": "Tiles",
        "price": 100.0 + (i * 10),
        "confidence": 95 - i,
    }
```

There is no PDF parsing, no Claude/Anthropic call, no OCR — the `products` a
client receives are fabricated constants with a fabricated `confidence`. This is
exactly the failure mode BK Foundry's evidence ledger exists to prevent: a
value with nothing real behind it.

## 2. Doubled directory nesting breaks the build

The three trees are each nested one level too deep:

```
backend/backend/{main.py, config.py, requirements.txt, __init__.py, .env.example}
frontend/frontend/{index.html, css/styles.css, js/app.js, js/config.js}
deployment/deployment/{Dockerfile, docker-compose.yml, railway.json, render.yaml}
```

`deployment/deployment/Dockerfile` assumes the *single*-nested layout, so it
cannot build against this repo:

```dockerfile
COPY backend/requirements.txt .      # real path is backend/backend/requirements.txt -> COPY fails
COPY backend/ .
CMD ["python", "-m", "uvicorn", "main:app", ...]   # after the copy, main.py is not at /app root
```

From the repo root there is no `backend/requirements.txt` (only
`backend/backend/requirements.txt`), so the image fails at the first `COPY`.
Static hosting that expects `frontend/index.html` likewise 404s — the file is at
`frontend/frontend/index.html`.

## 3. Declared-but-unused dependencies

`backend/backend/requirements.txt` declares 26 packages implying a full
extraction/OCR/DB/queue stack:

```
sqlalchemy, psycopg2-binary, anthropic, pytesseract, pdf2image, PyMuPDF,
python-docx, python-pptx, celery, redis, imagehash, opencv-python,
google-auth, google-api-python-client, aiofiles, httpx, requests, ...
```

`main.py` imports **none** of them — only `fastapi`, `uvicorn`, and the stdlib
(`os`, `uuid`, `json`, `typing`, `datetime`, `pathlib`). `DATABASE_URL`,
`REDIS_URL`, and `ANTHROPIC_API_KEY` are read into `Settings` and never used.
The only heavy dependency actually exercised is `python-multipart` (implicitly,
for the `UploadFile` form upload). The requirements list is aspirational, not a
description of what runs.

## 4. Frontend calls export endpoints the backend never routes

`frontend/frontend/js/app.js` offers three downloads:

```javascript
downloadExcel(): .../api/jobs/${id}/export/excel
downloadCSV():   .../api/jobs/${id}/export/csv
downloadJSON():  .../api/jobs/${id}/export/json
```

`backend/backend/main.py` defines no `/export/*` route — its only routes are
`/`, `/health`, `POST /api/jobs`, `GET /api/jobs/{id}`, `.../upload`,
`.../process`, `.../progress`, `.../products`. All three export buttons 404.

## 5. No `fly.toml` was ever tracked, yet the frontend targets Fly

`git log --all` finds no `fly.toml` in the history, and none exists in the tree.
The deployment configs that *are* present target Docker / Railway / Render
(`Dockerfile`, `docker-compose.yml`, `railway.json`, `render.yaml`) — not Fly.
Meanwhile `frontend/frontend/js/config.js` hardcodes:

```javascript
BACKEND_URL: "https://catalogai-pro.fly.dev"
```

So the frontend points at a Fly.io deployment for which this repo carries no
deploy configuration at all.

## Removal

The four items (`backend/`, `frontend/`, `deployment/`, old `README.md`) are
removed via tracked `git rm` in the same commit that adds this record. `LICENSE`
is kept. The pre-existing ruff `extend-exclude` for these directories is dropped
from `pyproject.toml`, since it existed only to keep this scaffold out of lint.
