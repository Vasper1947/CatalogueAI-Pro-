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

## Autonomy & approval policy

Once a plan is approved (or the task is unambiguous), **proceed without stopping
mid-way** as long as every step satisfies all of these:

- it stays within the task's **stated scope**;
- it touches **no file marked locked** (see "Locked dependency" above and any
  per-task locks) without explicit authorization for that specific file;
- it does **not lower a threshold, weaken a gate, or force a match/result to
  pass** — a weak honest result is reported, never massaged into a pass;
- it is **reversible via git** (committed history or recoverable working tree).

If something useful is **beyond the literal scope but still reversible**, do it
and **flag it clearly in the report** rather than stopping for it — unless it is
genuinely irreversible, in which case stop first.

**Always stop and ask** — no exceptions — for:

- **Promoting domain-knowledge `review_status` from `pending_review` to
  `confirmed`.** That judgement is the user's alone, per category, every time.
- **Anything that spends money or publishes/deploys externally** (sending data
  to an external service, deploying, posting, opening/merging PRs).
- **Anything that deletes or overwrites data without a git-recoverable path.**

When in doubt, prefer doing the reversible work and reporting it over stopping;
but never trade away one of the "always stop" items for momentum.

## Standing rules (stop restating these in every prompt)

- **Locked, never modified without explicit per-file authorization**:
  `packages/bkpack/**`, `packages/schemas/{parser,store,models}.py`,
  `tests/test_bkpack.py`. A task can lift the lock for one specific file for
  its own duration — that doesn't lift it for anything else, ever.
- **Never force a match, lower a threshold, or tune a rule so a specific case
  passes.** A threshold moves only with a stated structural reason grounded
  in real data — never to make one input produce a desired outcome.
- **Never fabricate a value, a source, or a test result.** A failing or
  ambiguous real result is a valid, reportable outcome — not a problem to
  make disappear.
- **Every new capability gets tested against real data, not only fixtures**,
  and the real result is reported honestly, whatever it is — including when
  it doesn't do what was hoped.
- **Constructed/synthetic test evidence is always labeled as such**, both in
  the test file itself and in any report about it — never presented as if it
  were a real scraped/captured result.
- **Every session ends with**: `ruff check .` clean, `pytest -v` green,
  changes committed, pushed, the push verified via `git ls-remote`, and
  `ROADMAP.md` updated to reflect what actually landed.
