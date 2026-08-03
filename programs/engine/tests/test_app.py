"""App tests: drive _run_job directly with a real (tiny) BK-PACK built via
bkpack.writer and monkeypatched schemas — no httpx, no disk store dependency.
"""

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from engine import app as app_module
from engine.app import (
    _JOBS,
    FLOOR_PRICE_NOTICE,
    IngestRequest,
    _run_job,
    get_engine,
    start_ingest,
)


class _StubBackground:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args):
        self.tasks.append((func, args))


def _make_bkpack(path, field_values):
    rows = [
        EvidenceRow(
            record_id="P1", field=k, value=v, source_uri="scrape://x",
            method="scrape", confidence=0.9,
        )
        for k, v in field_values.items()
    ]
    build_bkpack(
        str(path), evidence_rows=rows, media_files={},
        producer={"program": 3, "app_version": "test", "agent_id": "test"},
    )


def _schema(path, fields):
    return {
        "category_path": path,
        "fields": [
            {"name": n, "required": r, "locked": False, "is_formula": False}
            for n, r in fields
        ],
    }


def test_matched_ingest_has_floor_price_and_population(tmp_path, monkeypatch):
    bp = tmp_path / "m.bkpack.zip"
    _make_bkpack(bp, {"Brand": "Bosch", "Model": "X", "Voltage": "18"})
    monkeypatch.setattr(
        app_module, "load_schemas",
        lambda *a, **k: [_schema(
            ["Tools", "Drills"],
            [("Brand", True), ("Model", True), ("Voltage", False), ("Weight", False)],
        )],
    )
    _JOBS["m1"] = {"status": "queued"}

    _run_job("m1", str(bp))
    res = get_engine("m1")

    assert res["status"] == "template_matched"
    assert res["floor_price"] == FLOOR_PRICE_NOTICE            # fixed gate present
    assert res["detection"]["matched"] == ["Tools", "Drills"]
    assert res["population"]["status"] in ("ready_for_review", "incomplete")
    # ready_for_review is never labelled upload-ready anywhere
    assert "upload_ready" not in res


def test_unmatched_ingest_still_has_floor_price(tmp_path, monkeypatch):
    bp = tmp_path / "u.bkpack.zip"
    _make_bkpack(bp, {"totally": "x", "unrelated": "y", "otherthing": "z"})
    monkeypatch.setattr(
        app_module, "load_schemas",
        lambda *a, **k: [_schema(["Tools", "Drills"], [("Brand", True), ("Model", True)])],
    )
    _JOBS["u1"] = {"status": "queued"}

    _run_job("u1", str(bp))
    res = get_engine("u1")

    assert res["status"] == "no_template_match"
    assert res["population"] is None
    assert res["floor_price"] == FLOOR_PRICE_NOTICE            # present regardless of match
    assert "upload_ready" not in res


def test_start_ingest_registers_job_with_floor_price():
    bg = _StubBackground()
    resp = start_ingest(IngestRequest(bkpack_path="x.zip"), bg)

    assert resp["status"] == "queued"
    assert resp["floor_price"] == FLOOR_PRICE_NOTICE
    assert bg.tasks and bg.tasks[0][0] is _run_job
