"""BK Foundry's single command-line entry point: one product or category URL
in, one upload-ready ZIP out, end to end against the real pipeline --
discover -> scrape -> stage -> images/CSV -> detect -> populate -> write xlsx
-> package.

    python -m cli.main <url> [--out DIR] [--limit N] [--category-override "A > B > C"]

See ``build_arg_parser`` for every flag. Prints one progress line per
candidate product (captured / blocked / skipped, with a reason for the
latter two) and a final summary (captured / detected / written / blocked),
then writes a human-readable run report file into --out alongside the
produced ZIP(s) -- every run, not just a one-off.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from bkpack.evidence import EvidenceRow
from engine.app import load_schemas
from engine.batch import BatchRunSummary, run_batch
from export.staging import (
    finalize_zip,
    list_staged_records,
    load_staged_evidence_rows,
)
from export.upload import PackageResult, package_for_upload
from schemas.store import load_schema
from scraper.assemble import PRODUCER, build_pack_from_fields
from scraper.discover import (
    discover_links,
    extract_spec_table,
    extract_structured_data,
    fetch_bytes,
    fetch_html,
    find_media,
    resolve_product_image,
    robots_allows,
)

DEFAULT_LIMIT = 25
# A safety cap on how many category-page links are ever probed, independent
# of --limit (which caps successful CAPTURES) -- a real category page can
# link to far more than --limit non-product pages (nav, footer, blog...).
MAX_CANDIDATES_PROBED = 200


@dataclass
class CaptureOutcome:
    url: str
    status: str  # "captured" | "blocked" | "skipped"
    reason: str | None = None
    record_id: str | None = None
    image_captured: bool = False


@dataclass
class RunResult:
    job_id: str
    input_url: str
    is_category: bool
    candidates_tried: int
    captures: list[CaptureOutcome] = field(default_factory=list)
    batch_summary: BatchRunSummary | None = None
    packages: list[PackageResult] = field(default_factory=list)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli.main",
        description="Turn a product or category URL into a BK upload-ready ZIP.",
    )
    parser.add_argument("url", help="A product page URL, or a category/listing page URL.")
    parser.add_argument(
        "--out", default="bk_foundry_run", help="Output directory (default: ./bk_foundry_run)."
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Max products to capture from a category page (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--category-override", default=None, metavar="PATH",
        help=(
            "Force every captured product to a specific BK category, e.g. "
            '"Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > '
            'Edge Trim" -- skips automatic detection entirely. Use when you '
            "already know the category and detection can't confidently decide."
        ),
    )
    return parser


def _slug(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return safe or "run"


def _probe_page(url: str):
    """Fetch a page and extract everything the pipeline could use from it.
    Prefers a plain HTTP GET (see scraper.discover.fetch_html's own
    reasoning); returns (html, fields, spec_rows, media_refs) -- fields and
    spec_rows are both empty for a page with no usable product evidence at
    all (never guessed into looking like a product)."""
    html = fetch_html(url)
    if not html:
        from scraper.discover import _render_html  # lazy: optional Playwright dep

        html = _render_html(url)
    if not html:
        return None, {}, [], []
    fields = extract_structured_data(url, html=html)
    spec_rows = extract_spec_table(html)
    media_refs = find_media(html, url)
    return html, fields, spec_rows, media_refs


def discover_candidates(url: str, *, limit: int) -> tuple[list[str], bool, str | None]:
    """Return (candidate_urls, is_category, html_of_url). If url itself has
    usable product evidence, it is the sole candidate. Otherwise url is
    treated as a category/listing page and its same-domain links become
    candidates, capped at MAX_CANDIDATES_PROBED (independent of --limit,
    which caps successful captures, not probes)."""
    html, fields, spec_rows, _media = _probe_page(url)
    if html is None:
        return [], False, None
    if fields or spec_rows:
        return [url], False, html
    links = discover_links(html, url)
    return links[:MAX_CANDIDATES_PROBED], True, html


def capture_products(
    candidates: list[str], job_id: str, staging_root: Path, *, limit: int
) -> list[CaptureOutcome]:
    """Probe each candidate in turn, staging every real product found (crash-
    safe, immediately) until `limit` products are captured or candidates run
    out. Every candidate gets exactly one outcome -- captured, blocked
    (robots.txt), or skipped (no usable evidence) -- printed as it happens."""
    outcomes: list[CaptureOutcome] = []
    captured = 0
    for i, url in enumerate(candidates, start=1):
        if captured >= limit:
            break
        if not robots_allows(url):
            outcomes.append(CaptureOutcome(url=url, status="blocked", reason="disallowed by robots.txt"))
            print(f"[{i}/{len(candidates)}] BLOCKED  {url}  (robots.txt disallows)")
            continue
        try:
            html, fields, spec_rows, media_refs = _probe_page(url)
        except Exception as exc:  # noqa: BLE001 -- one bad candidate must not abort the run
            outcomes.append(CaptureOutcome(url=url, status="skipped", reason=f"fetch error: {exc}"))
            print(f"[{i}/{len(candidates)}] SKIPPED  {url}  (fetch error: {exc})")
            continue
        if html is None:
            outcomes.append(CaptureOutcome(url=url, status="skipped", reason="page could not be fetched"))
            print(f"[{i}/{len(candidates)}] SKIPPED  {url}  (could not fetch)")
            continue
        if not fields and not spec_rows:
            outcomes.append(CaptureOutcome(url=url, status="skipped", reason="no usable evidence on page"))
            print(f"[{i}/{len(candidates)}] SKIPPED  {url}  (no usable evidence)")
            continue

        image_bytes_list = []
        image_url = resolve_product_image(fields, html, url)
        if image_url:
            raw = fetch_bytes(image_url)
            if raw:
                image_bytes_list.append(raw)

        rows = build_pack_from_fields(
            fields, url, str(staging_root / f"{job_id}.discard.bkpack.zip"),
            page_html=html, job_id=job_id, staging_root=staging_root,
            image_bytes_list=image_bytes_list or None,
        )
        if not rows:
            outcomes.append(
                CaptureOutcome(url=url, status="skipped", reason="no evidence rows assembled")
            )
            print(f"[{i}/{len(candidates)}] SKIPPED  {url}  (no evidence rows assembled)")
            continue

        record_id = rows[0].record_id
        captured += 1
        outcomes.append(
            CaptureOutcome(url=url, status="captured", record_id=record_id, image_captured=bool(image_bytes_list))
        )
        print(
            f"[{i}/{len(candidates)}] CAPTURED {url}  "
            f"(record={record_id}, {len(rows)} evidence fields, {len(media_refs)} media refs, "
            f"image={'yes' if image_bytes_list else 'no'})"
        )
    return outcomes


def _resolve_category_override(path_text: str) -> dict:
    parts = [p.strip() for p in path_text.split(">") if p.strip()]
    return load_schema(parts)


def run(args: argparse.Namespace) -> RunResult:
    out_dir = Path(args.out)
    staging_root = out_dir / "staging"
    xlsx_dir = out_dir / "xlsx"
    upload_dir = out_dir / "upload"
    for d in (out_dir, staging_root, xlsx_dir, upload_dir):
        d.mkdir(parents=True, exist_ok=True)

    job_id = f"{_slug(args.url)}-{int(time.time())}"
    print(f"BK Foundry run {job_id!r} for: {args.url}")

    if not robots_allows(args.url):
        print("BLOCKED: robots.txt disallows this URL. Nothing fetched.")
        return RunResult(job_id=job_id, input_url=args.url, is_category=False, candidates_tried=0)

    candidates, is_category, html = discover_candidates(args.url, limit=args.limit)
    if html is None:
        print("SKIPPED: the page could not be fetched at all.")
        return RunResult(job_id=job_id, input_url=args.url, is_category=False, candidates_tried=0)
    kind = "category page" if is_category else "product page"
    print(f"Discovered as a {kind}: {len(candidates)} candidate URL(s) to probe.")

    captures = capture_products(candidates, job_id, staging_root, limit=args.limit)

    record_ids = list_staged_records(job_id, staging_root=staging_root)
    bkpack_path = out_dir / f"{job_id}.bkpack.zip"
    if record_ids:
        finalize_zip(job_id, str(bkpack_path), staging_root=staging_root, producer=PRODUCER)

    result = RunResult(
        job_id=job_id, input_url=args.url, is_category=is_category,
        candidates_tried=len(captures), captures=captures,
    )
    if not record_ids:
        print("No products were captured -- nothing to detect/populate/write.")
        return result

    records: list[tuple[str, list[dict]]] = []
    for record_id in record_ids:
        evidence_rows: list[EvidenceRow] = load_staged_evidence_rows(
            job_id, record_id, staging_root=staging_root
        )
        records.append((record_id, [r.to_dict() for r in evidence_rows]))

    forced_schema = _resolve_category_override(args.category_override) if args.category_override else None
    schemas = [forced_schema] if forced_schema is not None else load_schemas()
    summary = run_batch(
        records, schemas, xlsx_dir, base_filename=_slug(args.url), forced_schema=forced_schema
    )
    result.batch_summary = summary

    for wf in summary.written_files:
        media_files: dict[str, bytes] = {}
        for record_id in wf.record_ids:
            record_dir = staging_root / job_id / record_id
            for webp_path in sorted(record_dir.glob("*.webp")):
                media_files[webp_path.name] = webp_path.read_bytes()
        zip_name = Path(wf.output_path).stem + "_upload.zip"
        pkg = package_for_upload(wf.output_path, media_files, upload_dir / zip_name)
        result.packages.append(pkg)

    _print_final_summary(result)
    _write_report(result, out_dir)
    return result


def _print_final_summary(result: RunResult) -> None:
    captured = sum(1 for c in result.captures if c.status == "captured")
    blocked = sum(1 for c in result.captures if c.status == "blocked")
    skipped = sum(1 for c in result.captures if c.status == "skipped")
    images = sum(1 for c in result.captures if c.image_captured)
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print(f"  candidates tried : {result.candidates_tried}")
    print(f"  captured         : {captured}")
    print(f"  images captured  : {images}")
    print(f"  blocked          : {blocked}")
    print(f"  skipped          : {skipped}")
    if result.batch_summary is not None:
        s = result.batch_summary
        print(f"  detected/matched : {len(s.matched)}")
        print(f"  no_template_match: {len(s.no_template_match)}")
        print(f"  category_ambiguous: {len(s.category_ambiguous)}")
        print(f"  xlsx files written: {len(s.written_files)}")
        print(f"  write failures   : {len(s.write_failures)}")
    for pkg in result.packages:
        print(f"  package -> {pkg.output_path}")
        if pkg.missing_media:
            print(f"    missing media (referenced, not supplied): {pkg.missing_media}")
        if pkg.unreferenced_media:
            print(f"    unreferenced media (supplied, not referenced): {pkg.unreferenced_media}")
    print("=" * 60)


def _column_fill_stats(row_results) -> dict[str, dict[str, int]]:
    names: set[str] = set()
    for r in row_results:
        names.update(r.written_fields, r.blank_needs_input, r.blank_invalid_dropdown,
                      r.blank_unresolved_numeric, r.blank_never_populate, r.blank_variant_candidate)
    stats: dict[str, dict[str, int]] = {}
    for name in sorted(names):
        stats[name] = {
            "written": sum(1 for r in row_results if name in r.written_fields),
            "needs_input": sum(1 for r in row_results if name in r.blank_needs_input),
            "invalid_dropdown": sum(1 for r in row_results if name in r.blank_invalid_dropdown),
            "unresolved_numeric": sum(1 for r in row_results if name in r.blank_unresolved_numeric),
            "never_populate": sum(1 for r in row_results if name in r.blank_never_populate),
            "variant_candidate": sum(1 for r in row_results if name in r.blank_variant_candidate),
        }
    return stats


def _write_report(result: RunResult, out_dir: Path) -> Path:
    lines: list[str] = []
    lines.append("BK Foundry run report")
    lines.append(f"job_id: {result.job_id}")
    lines.append(f"input_url: {result.input_url}")
    lines.append(f"kind: {'category page' if result.is_category else 'product page'}")
    lines.append("")
    lines.append(f"candidates tried: {result.candidates_tried}")
    images = sum(1 for c in result.captures if c.image_captured)
    captured = sum(1 for c in result.captures if c.status == "captured")
    lines.append(f"images captured: {images}/{captured}")
    for c in result.captures:
        if c.reason:
            detail = f" ({c.reason})"
        else:
            detail = f" (record={c.record_id}, image={'yes' if c.image_captured else 'no'})"
        lines.append(f"  {c.status.upper():9s} {c.url}{detail}")
    lines.append("")

    s = result.batch_summary
    if s is None:
        lines.append("No products captured -- detection/population/writing never ran.")
    else:
        lines.append(f"matched: {len(s.matched)}")
        lines.append(f"no_template_match: {len(s.no_template_match)}")
        for o in s.no_template_match:
            lines.append(f"  {o.record_id}: {o.reason}")
        lines.append(f"category_ambiguous: {len(s.category_ambiguous)}")
        for o in s.category_ambiguous:
            lines.append(f"  {o.record_id}: {o.reason}")
        lines.append(f"write_failures: {len(s.write_failures)}")
        for wfail in s.write_failures:
            lines.append(f"  {wfail.category_path}: {wfail.error}")
        lines.append("")

        for wf in s.written_files:
            lines.append(f"written file: {wf.output_path}")
            lines.append(f"  category: {' > '.join(wf.category_path)}")
            lines.append(f"  rows: {len(wf.record_ids)} ({', '.join(wf.record_ids)})")
            stats = _column_fill_stats(wf.row_results)
            n = len(wf.row_results)
            lines.append("  per-column fill rate:")
            for name, st in stats.items():
                rate = st["written"] / n if n else 0.0
                blank_reasons = ", ".join(
                    f"{k}={v}" for k, v in st.items() if k != "written" and v
                )
                lines.append(
                    f"    {name}: {st['written']}/{n} ({rate:.0%})"
                    + (f"  [{blank_reasons}]" if blank_reasons else "")
                )
            lines.append("")

    for pkg in result.packages:
        lines.append(f"package: {pkg.output_path}")
        lines.append(f"  media_written: {pkg.media_written}")
        lines.append(f"  missing_media: {pkg.missing_media}")
        lines.append(f"  unreferenced_media: {pkg.unreferenced_media}")
        lines.append("")

    report_path = out_dir / f"{result.job_id}_report.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRun report written to: {report_path}")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
