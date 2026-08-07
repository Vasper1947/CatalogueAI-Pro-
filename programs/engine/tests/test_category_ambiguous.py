"""The /ingest path (Task 2): a genuinely-tied, unresolved match must report a
distinct "category_ambiguous" status listing every tied candidate, and must
NEVER proceed to populate.py against an arbitrarily-picked one of them.
"""

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from engine import app as app_module
from engine import populate as populate_module
from engine.app import _JOBS, _run_job, get_engine


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


def test_ambiguous_tie_reports_distinct_status_with_all_tied_candidates(tmp_path, monkeypatch):
    bp = tmp_path / "ambig.bkpack.zip"
    _make_bkpack(bp, {"Material": "Aluminum", "Length": "2.5 m"})
    # Two shape-named siblings, identical shape, no distinguishing evidence text
    # -> a genuine, unresolvable tie.
    corner = _schema(
        ["Family", "Sub", "Corner Profile"], [("Material", True), ("Length", True)]
    )
    edge = _schema(["Family", "Sub", "Edge Trim"], [("Material", True), ("Length", True)])
    monkeypatch.setattr(app_module, "load_schemas", lambda *a, **k: [corner, edge])
    _JOBS["ambig1"] = {"status": "queued"}

    _run_job("ambig1", str(bp))
    res = get_engine("ambig1")

    assert res["status"] == "category_ambiguous"
    assert res["population"] is None
    assert res["detection"]["matched"] is None
    tied = res["detection"]["tied_candidates"]
    assert len(tied) == 2
    assert {tuple(c["category_path"]) for c in tied} == {
        ("Family", "Sub", "Corner Profile"),
        ("Family", "Sub", "Edge Trim"),
    }
    for c in tied:
        assert "score" in c and "recall" in c
    assert res["floor_price"]["status"] == "pending_manual"  # fixed gate still present


def test_ambiguous_tie_never_calls_populate_from_evidence(tmp_path, monkeypatch):
    bp = tmp_path / "ambig2.bkpack.zip"
    _make_bkpack(bp, {"Material": "Aluminum", "Length": "2.5 m"})
    corner = _schema(
        ["Family", "Sub", "Corner Profile"], [("Material", True), ("Length", True)]
    )
    edge = _schema(["Family", "Sub", "Edge Trim"], [("Material", True), ("Length", True)])
    monkeypatch.setattr(app_module, "load_schemas", lambda *a, **k: [corner, edge])

    calls = []
    monkeypatch.setattr(
        app_module,
        "populate_from_evidence",
        lambda *a, **k: calls.append((a, k)) or populate_module.populate_from_evidence(*a, **k),
    )
    _JOBS["ambig3"] = {"status": "queued"}

    _run_job("ambig3", str(bp))
    res = get_engine("ambig3")

    assert res["status"] == "category_ambiguous"
    assert calls == []  # populate_from_evidence was never invoked


def test_resolved_content_tie_break_still_populates_normally(tmp_path, monkeypatch):
    # A tie that DOES resolve (via content) must behave exactly like an
    # ordinary match: template_matched, population runs against the winner.
    bp = tmp_path / "resolved.bkpack.zip"
    _make_bkpack(bp, {
        "Material": "Aluminum", "Length": "2.5 m",
        "Applications": "a corner solution for tiles",
    })
    corner = _schema(
        ["Family", "Sub", "Corner Profile"], [("Material", True), ("Length", True)]
    )
    edge = _schema(["Family", "Sub", "Edge Trim"], [("Material", True), ("Length", True)])
    monkeypatch.setattr(app_module, "load_schemas", lambda *a, **k: [corner, edge])
    _JOBS["resolved1"] = {"status": "queued"}

    _run_job("resolved1", str(bp))
    res = get_engine("resolved1")

    assert res["status"] == "template_matched"
    assert res["detection"]["matched"] == ["Family", "Sub", "Corner Profile"]
    assert res["population"] is not None
