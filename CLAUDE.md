# BK Foundry — working agreement

This repo hosts BK's catalog-automation programs. The pre-existing `backend/`,
`frontend/`, and `deployment/` directories are the CatalogAI Pro web app and
are separate from the Foundry work described here.

## The one non-negotiable rule: no evidence, no value

Every product field we ever emit is in exactly one of two states:

1. **A value, backed by a `source_uri`** it was actually read from.
2. **An explicit, confirmed absence** — `absence=True`, `value=None`: we looked
   and it genuinely is not stated in any source.

There is no third state. A field is never silently blank, and a value never
exists without something to point at. We do not guess, infer, or "fill in"
catalog data — a plausible-looking value with no source is a fabrication, and
fabrication is the exact failure this whole project exists to prevent.

### How `packages/bkpack` enforces it

- `evidence.py` — `EvidenceRow` validates on construction and **raises** if a
  row breaks the rule, so a bad row can't even be built, let alone published.
  `validate_row_dict` is a pure function reused at read time.
- `validator.py` — the deterministic gate every BK-PACK passes before Program 3
  touches it. It re-derives every check from the raw ZIP bytes (structure,
  SHA-256 integrity, and row consistency), so a hand-edited, corrupted, or
  maliciously-crafted pack is caught **independently of the writer** — being
  built by `build_bkpack` earns a pack no trust.
- `writer.py` / `reader.py` / `spec.py` — assemble and read the BK-PACK ZIP
  (`datapackage.json`, `evidence.jsonl`, `manifest-sha256.txt`, `media/`).

## Locked dependency — do not modify without explicit instruction

**`packages/bkpack/` and `tests/test_bkpack.py` are a locked, tested
dependency.** Everything downstream relies on their exact behaviour. Do not
edit, refactor, or "improve" them unless a task explicitly says to. If a change
seems necessary, stop and ask first. Treat them as frozen once green.

## Conventions

- **Paths**: always forward slashes (`packages/bkpack/writer.py`), including in
  code, docs, and BK-PACK internal paths — never backslashes.
- **Logging**: structured JSON only, via `common.logging.get_logger`. One JSON
  object per line; bind a `correlation_id` per job/request so a unit of work is
  traceable end to end. No bare `print` for operational logging.
- **Errors**: raise from the `common.errors.AppError` hierarchy, not bare
  exceptions, so failures carry a stable `code` and structured `details`.
- **Formatting & lint**: `ruff` is the single source of truth. `ruff check .`
  must be clean. No per-file ignores; scope with directory excludes if needed.
- **Tests**: every module ships with `pytest` tests that prove behaviour, not
  just "it runs". Test the failure modes you built the code to catch.
- **Library APIs**: if you are unsure how an installed library behaves, **read
  the installed package** (its source/signatures) — do not invent an API from
  memory. The same "no guessing" discipline we apply to catalog data.

## Definition of done

**A task is not done until its tests are green.** No "should work", no skipped
tests to force a pass. Run `python -m pytest -v` and `ruff check .`; both must
pass before the task is considered complete.

## Environment notes

- Use `python` on this machine — `python3` resolves to a non-functional Windows
  Store alias here.
- Install the workspace with `pip install -e .`; `bkpack` and `common` are then
  importable with no `PYTHONPATH` hacks.

## Build order

Program 1 (scraper) -> Program 4 (PDF worker) -> Program 3 (engine) ->
Program 2 (field app).

**Do not begin real Program 3 work until real BK Excel templates are confirmed
available** — do not build template-detection logic against a guessed
structure. That would be the same fabrication failure as inventing catalog
data, just applied to the template format.
