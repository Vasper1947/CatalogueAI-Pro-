"""API-surface tests for the scraper.

These drive the route and job functions directly (no ASGI TestClient, which
would pull in httpx) so no new dependency is needed and no live fetch happens.
The assemble + BK-PACK path runs for real.
"""

from scraper import app as app_module
from scraper.app import _JOBS, ScrapeRequest, _run_job, get_scrape, start_scrape


class _StubBackground:
    """Captures scheduled background tasks instead of running them."""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args):
        self.tasks.append((func, args))


def test_start_scrape_registers_a_queued_job_and_schedules_the_pipeline():
    bg = _StubBackground()
    resp = start_scrape(ScrapeRequest(url="https://example.com/products/1"), bg)

    assert resp["status"] == "queued"
    job_id = resp["job_id"]
    assert _JOBS[job_id]["status"] == "queued"
    # The pipeline is scheduled, not run inline.
    assert bg.tasks and bg.tasks[0][0] is _run_job


def test_run_job_completes_and_attaches_sourced_evidence(monkeypatch):
    url = "https://example.com/products/1"
    monkeypatch.setattr(app_module, "robots_allows", lambda page_url: True)
    monkeypatch.setattr(
        app_module,
        "extract_structured_data",
        lambda page_url: {"name": "Aluminum Tile Trim", "sku": "S1", "price": "2.35"},
    )
    _JOBS["job-done"] = {"status": "queued", "url": url}

    _run_job("job-done", url)
    result = get_scrape("job-done")

    assert result["status"] == "done"
    assert result["fields"]["sku"] == "S1"
    assert result["evidence"]
    assert all(row["source_uri"] == url for row in result["evidence"])


def test_run_job_refuses_disallowed_url_without_fetching(monkeypatch):
    url = "https://example.com/products/x"
    calls = {"extract": 0}

    def spy_extract(page_url: str) -> dict:
        calls["extract"] += 1
        return {"name": "should not happen"}

    monkeypatch.setattr(app_module, "robots_allows", lambda page_url: False)
    monkeypatch.setattr(app_module, "extract_structured_data", spy_extract)
    _JOBS["job-refused"] = {"status": "queued", "url": url}

    _run_job("job-refused", url)
    result = get_scrape("job-refused")

    assert result["status"] == "refused"
    assert "robots.txt" in result["reason"]
    assert calls["extract"] == 0  # nothing was fetched after the refusal
