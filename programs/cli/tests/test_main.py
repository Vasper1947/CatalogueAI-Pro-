"""CLI orchestration tests: the pure-logic pieces (arg parsing, candidate
discovery, capture-loop decisions, reporting) exercised with monkeypatched
network boundaries -- no live network in tests."""

from cli.main import (
    CaptureOutcome,
    RunResult,
    _column_fill_stats,
    _resolve_category_override,
    _slug,
    _write_report,
    build_arg_parser,
    capture_products,
    discover_candidates,
)
from engine.batch import BatchRunSummary, RecordOutcome, WriteFailure, WrittenFile
from engine.writer import RowWriteResult


def test_arg_parser_defaults():
    args = build_arg_parser().parse_args(["https://example.com/p/1"])
    assert args.url == "https://example.com/p/1"
    assert args.out == "bk_foundry_run"
    assert args.limit == 25
    assert args.category_override is None


def test_arg_parser_flags():
    args = build_arg_parser().parse_args([
        "https://example.com/cat", "--out", "run1", "--limit", "5",
        "--category-override", "A > B > C",
    ])
    assert args.out == "run1"
    assert args.limit == 5
    assert args.category_override == "A > B > C"


def test_slug_strips_non_alnum():
    assert _slug("https://example.com/cat?x=1&y=2") == "https_example_com_cat_x_1_y_2"


def test_slug_never_empty():
    assert _slug("###") == "run"


def test_discover_candidates_single_product_page(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(
        cli_main, "_probe_page",
        lambda url: ("<html></html>", {"name": "Widget"}, [], []),
    )
    candidates, is_category, html = discover_candidates("https://example.com/p/1", limit=10)
    assert candidates == ["https://example.com/p/1"]
    assert is_category is False
    assert html == "<html></html>"


def test_discover_candidates_category_page_uses_links(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(cli_main, "_probe_page", lambda url: ("<html>cat</html>", {}, [], []))
    monkeypatch.setattr(
        cli_main, "discover_links",
        lambda html, url: ["https://example.com/p/1", "https://example.com/p/2"],
    )
    candidates, is_category, _html = discover_candidates("https://example.com/cat", limit=10)
    assert candidates == ["https://example.com/p/1", "https://example.com/p/2"]
    assert is_category is True


def test_discover_candidates_unfetchable_page(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(cli_main, "_probe_page", lambda url: (None, {}, [], []))
    candidates, _is_category, html = discover_candidates("https://example.com/x", limit=10)
    assert candidates == []
    assert html is None


def test_capture_products_stops_at_limit(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(cli_main, "robots_allows", lambda url: True)
    monkeypatch.setattr(
        cli_main, "_probe_page",
        lambda url: ("<html></html>", {"name": "Widget"}, [], []),
    )
    monkeypatch.setattr(cli_main, "fetch_bytes", lambda url: None)

    class _FakeRow:
        record_id = "rec-1"

    monkeypatch.setattr(cli_main, "build_pack_from_fields", lambda *a, **k: [_FakeRow()])

    candidates = [f"https://example.com/p/{i}" for i in range(5)]
    outcomes = capture_products(candidates, "job1", tmp_staging_root(), limit=2)

    assert sum(1 for o in outcomes if o.status == "captured") == 2
    assert len(outcomes) == 2  # loop stops once the limit is reached


def test_capture_products_reports_robots_block(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(cli_main, "robots_allows", lambda url: False)
    outcomes = capture_products(["https://example.com/p/1"], "job1", tmp_staging_root(), limit=5)
    assert outcomes[0].status == "blocked"
    assert "robots" in outcomes[0].reason


def test_capture_products_reports_no_usable_evidence(monkeypatch):
    import cli.main as cli_main

    monkeypatch.setattr(cli_main, "robots_allows", lambda url: True)
    monkeypatch.setattr(cli_main, "_probe_page", lambda url: ("<html></html>", {}, [], []))
    outcomes = capture_products(["https://example.com/p/1"], "job1", tmp_staging_root(), limit=5)
    assert outcomes[0].status == "skipped"
    assert outcomes[0].reason == "no usable evidence on page"


def test_resolve_category_override_splits_on_arrow(monkeypatch):
    import cli.main as cli_main

    seen = {}

    def _fake_load_schema(parts):
        seen["parts"] = parts
        return {"category_path": parts}

    monkeypatch.setattr(cli_main, "load_schema", _fake_load_schema)
    schema = _resolve_category_override("Floor & Wall Finishes > Tile Accessories > Edge Trim")
    assert seen["parts"] == ["Floor & Wall Finishes", "Tile Accessories", "Edge Trim"]
    assert schema["category_path"] == seen["parts"]


def test_column_fill_stats_counts_every_bucket():
    rows = [
        RowWriteResult(written_fields=["Brand"], blank_needs_input=["Color"]),
        RowWriteResult(written_fields=[], blank_needs_input=["Brand"], blank_invalid_dropdown=["Color"]),
    ]
    stats = _column_fill_stats(rows)
    assert stats["Brand"]["written"] == 1
    assert stats["Brand"]["needs_input"] == 1
    assert stats["Color"]["needs_input"] == 1
    assert stats["Color"]["invalid_dropdown"] == 1


def test_write_report_creates_a_real_file(tmp_path):
    summary = BatchRunSummary(
        total_records=1,
        matched=[RecordOutcome(record_id="p1", status="matched", category_path=["Cat", "Widget"])],
        no_template_match=[RecordOutcome(record_id="p2", status="no_template_match", reason="no schema qualified")],
        written_files=[
            WrittenFile(
                output_path=str(tmp_path / "out.xlsx"), category_path=["Cat", "Widget"],
                record_ids=["p1"],
                row_results=[RowWriteResult(written_fields=["Brand"], blank_needs_input=["Color"])],
            )
        ],
        write_failures=[WriteFailure(category_path=["Cat", "X"], record_ids=["p3"], error="boom")],
    )
    result = RunResult(
        job_id="job1", input_url="https://example.com/cat", is_category=True,
        candidates_tried=2,
        captures=[CaptureOutcome(url="https://example.com/p/1", status="captured", record_id="p1")],
        batch_summary=summary,
    )

    report_path = _write_report(result, tmp_path)

    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "job1" in text
    assert "p1" in text
    assert "no schema qualified" in text
    assert "boom" in text
    assert "Brand" in text


def tmp_staging_root():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())
