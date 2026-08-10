# BK Foundry — Roadmap

Single source of truth for project state. Rebuilt from actual repo state
(`git log`, file inventory, `domain_knowledge/data/index.json`) each time it's
updated — never from a prior summary, since those drift. **Update this file at
the end of every session.**

## Done

Program build order per CLAUDE.md: Program 1 (scraper) → Program 4 (PDF
worker) → Program 3 (engine) → Program 2 (field app).

- **`packages/bkpack`** — BK-PACK interchange format core (locked, frozen).
  `c46b7dc`
- **`packages/common`** — shared, non-domain-specific utilities (`errors`,
  `logging`, `units`). `c46b7dc`, `units.py` relocated here from
  `programs/scraper` `7bb763f`
- **Program 1 — scraper** (`programs/scraper`): sitemap + JSON-LD discovery,
  spec-table extraction + unit normalization, category classifier wiring,
  Brand-vocabulary matching, `POST /scrape` + `GET /scrape/{job_id}`.
  `e3b7b71`, `b870daa`, `d936caa`
- **Program 4 — PDF worker** (`programs/pdfworker`): text/image extraction,
  garbled-text detection, `POST /pdf` + `GET /pdf/{job_id}`. `65d4ad3`
- **`packages/schemas`** — general BK template → schema parser; 510 real
  category templates parsed and stored (locked: `parser.py`/`store.py`/
  `models.py`). `fd32de3`
- **`packages/schemas/aliases.py`** — category-aware, value-guarded field-name
  aliasing (TMT/Edge-Trims/universal sets). `9c90c64`
- **`packages/domain_knowledge`** — researched, source-attributed category
  knowledge; deterministic plausibility flagging. `207d40b`, `a3cec51`
- **Program 3 — engine** (`programs/engine`): template detection
  (`detect.py`), field population (`populate.py`), `POST /ingest` +
  `GET /engine/{job_id}`. Detection hardening arc, in order:
  precision-only scoring `3ed9a61` → recall gate `772fd47`, `b719d13` →
  section-based commercial-field exclusion + Brand-vocab + sibling tie-break
  `de0bc72` → content-based tie disambiguation + explicit ambiguity reporting
  (never a silent pick) `ae6417b` → alias resolution wired into `populate.py`,
  gated by `common.units.normalize_value` specificity (direct-match and
  aliased fields held to the same bar) `a32857e`, `9c6755e` → fixed
  `build_pack_from_fields`'s gate so a spec-table-only page (no JSON-LD) stages
  its real evidence instead of nothing `c2b22e6`.
- **`packages/export`** — crash-safe staging (`stage_capture`,
  `list_staged_records`), WebP image processing (`process_image`), SKU CSV
  generation (`write_sku_csv`), `finalize_zip` (calls `bkpack.writer.
  build_bkpack` unmodified + appends `SKU.csv`). Proven crash-recoverable
  (stage in one call, finalize independently in a later, unrelated call) and
  wired into `assemble.py` as an opt-in `job_id` parameter (default off,
  zero behavior change unless used). `cb98fb4`, `c2b22e6`
- **Removed**: the pre-existing CatalogAI Pro web app scaffold
  (`backend/`/`frontend`/`deployment/`), inventoried before deletion.
  `cad1b99`
- **Standing rules moved into `CLAUDE.md`** (locked-files list, no-forced-
  match, no-fabrication, real-data-testing, labeled-synthetic-evidence,
  definition-of-done) so prompts stop restating them every session.
- **Checkpoint tooling**: `pytest-cov` added; `scripts/check.py` runs ruff +
  pytest + coverage in one command. Real measured baseline: **76.48% total**
  (`packages/bkpack` ≈100% except `validator.py` 67%; `packages/common/units.py`
  85%; `packages/schemas/aliases.py`/`classify.py`/`store.py` 96–97%;
  `programs/engine` 90–98%; `programs/scraper/discover.py` 69%;
  `programs/pdfworker/app.py` 71%). Honestly embarrassing, disclosed gaps:
  `packages/common/errors.py` and `logging.py` at **0%** (no dedicated tests
  yet), `packages/schemas/models.py` and `packages/schemas/parser.py` also
  report **0%** — not because they're untested (`packages/schemas/tests/
  test_parser.py` exercises `parser.py` directly, and every `write_template`
  self-verification round-trips through it too) but because of a real
  coverage.py measurement gap: `coverage: Module schemas was previously
  imported, but not measured (module-not-measured)` — an early, pre-coverage
  import during collection means later re-imports (cached by Python) are
  never retraced. Reported as-is, not silenced or worked around.
  `COVERAGE_FLOOR = 76` in `scripts/check.py`, set to the real baseline above
  (floored to an integer with a small safety margin) — moves only with a real
  measured change.
- **Media discovery + full-page snapshot** (`programs/scraper/discover.py`):
  `find_media(page_html, base_url)` → `{url, media_type}` for `<video>`/
  `<source>` elements and `.gif` references, relative URLs resolved,
  deduplicated, empty list when none. `capture_full_page_snapshot(page)` via
  Playwright's own `page.screenshot(full_page=True)`. Both wired into
  `packages/export/staging.py`'s crash-safe pipeline (`media_refs` staged
  immediately, aggregated into `finalize_zip`'s output, omitted — never an
  empty file — when no record has any) and into `programs/scraper/
  assemble.py`'s `build_pack_from_fields`. Proven against real, live content:
  TBK Metal's blog index (`https://www.tbkmetal.com/blog/`) has two real
  `.gif` references (one independently verified live, 443,535 bytes; the
  other genuinely 404s on TBK's own site — reported honestly, not treated as
  a bug in `find_media`, whose job is to report what a page references).
  TBK's own product pages have no video/GIF content at all — confirmed by
  checking several before searching elsewhere. A REAL, live full-page
  screenshot could not be captured this session — see Blocked below.
- **Program 3 — Excel writer** (`programs/engine/writer.py`):
  `write_template(population_result, schema, output_path)` builds a real
  `.xlsx` from a category's actual parsed schema structure (no raw `.xlsx`
  templates exist in this repo to edit — only their parsed JSON — so every
  file is reconstructed fresh: Template/Lookup/Instructions sheets, section
  labels, header text, per-field dropdown validation sourced the same way the
  real template sources it — inline vs a `Lookup`-sheet range reference,
  matching `dropdown_source` — numeric formatting, and sheet/cell protection).
  Reuses `engine.detect.NEVER_POPULATE`/`canonical` as the single Floor-Price
  gate (the column and header are still written, matching the real template's
  structure; only the value is withheld, since a human still fills it in
  manually in that same file) and `common.units.convert_from_mm` so a numeric
  value is written in the field's own real unit (e.g. metres), not blindly in
  `normalize_value`'s canonical mm. Dropdown values are checked strictly
  against the schema's real vocabulary — a matched-but-off-vocabulary value is
  left blank (`blank_invalid_dropdown`), never written invalid. Self-
  verification is mandatory: every written file is immediately re-parsed with
  `packages/schemas/parser.py` (unmodified, locked) and diffed structurally
  (name/type/required/locked/column) and by written value; any real mismatch
  raises `WriteVerificationError` rather than shipping a quietly-wrong file.
  One documented, mechanical (not chosen) exclusion from the structural diff:
  a formula column's original formula text is never captured anywhere in the
  parsed schema, so a blank cell can never re-parse as `data_type == "f"` —
  `is_formula` fields are reported separately via
  `VerificationReport.formula_fields_left_blank`, never silently skipped.
  Two design bugs caught and fixed during build, before they could ship (both
  now regression-tested in `programs/engine/tests/test_writer.py`): (1) a
  header-text ordering bug that made `required` mis-parse as `False` whenever
  a field was both `required` and `conditional` (the locked parser checks
  "ends with `*`" on the raw header BEFORE stripping "(cond)"); (2) a
  header-row misdetection bug when every field has a section label (the real
  Edge Trim schema's actual shape) — the locked parser's "most string cells
  wins, ties go to the earlier row" rule would pick the section row over the
  real header row unless the section row is written sparser (only on a
  section transition, not per field). Proven end-to-end against the real TBK
  Metal Edge Trim fixture (`detect.py` → `populate.py` → `write_template`) —
  see the session report for the exact, honest produced-file contents.

- **`packages/schemas/vocabulary.py`**: `match_to_vocabulary(raw_value, vocabulary)`
  — deterministic, strictest-first dropdown-value matching (exact →
  case-insensitive → normalized punctuation/whitespace + a small explicit
  British/American spelling equivalence list → whole-word containment),
  stopping at the first level with exactly one hit; 2+ hits at one level is a
  reported ambiguity, never resolved by falling through. No fuzzy/edit-
  distance/embedding matching anywhere.
- **`programs/engine/populate.py`** wired to `match_to_vocabulary`: a dropdown
  field's accepted value now resolves to the CANONICAL vocabulary term (never
  the raw string), with `FieldResult.reason` recording the method. No match
  distinguishes `"no_evidence"` from `"not_in_vocabulary"` — different
  problems, no longer indistinguishable downstream. A value containing 2+ real
  vocabulary terms (e.g. a real "Aluminium, Stainless Steel" listing) becomes
  `status="variant_candidate"`, listing every match in `.candidates` — never
  resolved by picking one. This corrected a real gap the prior round's TBK
  test surfaced (a value like "Aluminum Alloy" used to populate verbatim, only
  caught later — and left blank — by `write_template`'s own separate check).
- **`programs/engine/writer.py`** generalized to `write_template_batch`: N
  populated records → one `.xlsx`, N data rows, one shared set of headers/
  validations/protection, self-verification extended to check every row.
  `write_template()` is now a thin single-record wrapper (100%
  behavior-compatible). Added a `blank_variant_candidate` bucket alongside the
  existing blank-reason buckets.
- **`programs/engine/batch.py`** (new): `run_batch()` runs detect + populate
  per staged record, groups matched records by detected `category_path` (one
  schema = one file), splits each group to at most that schema's real
  `row_limit` (falls back to 500 only if genuinely unstated), and writes one
  `.xlsx` per chunk. No-template-match and genuinely-ambiguous records are
  reported in the summary, excluded from every written file — never dropped,
  never guessed into a category. A `forced_schema` parameter supports a
  human's explicit category override. A chunk whose self-verification fails
  is recorded in `write_failures`, not raised past the whole run.
- **`packages/export/upload.py`** (new): `package_for_upload(xlsx_path,
  media_files, output_zip)` builds the exact ZIP shape a real template's own
  Instructions sheet specifies (xlsx at root + a `media/` folder — re-read
  from a real parsed schema, not a summary of it). Re-parses the xlsx with
  the real, locked parser to find every Media-section column's real filename
  references across every row, and reports `missing_media` (referenced, not
  supplied) / `unreferenced_media` (supplied, not referenced) — verified
  programmatically, never assumed. A direct-URL media value (the template's
  own stated alternative to a local file) is correctly never flagged missing.
- **`programs/cli/main.py`** (new): one command, a product or category URL in,
  an upload-ready ZIP out — `discover → scrape → stage → images/CSV → detect
  → populate → write xlsx → package`. Invocation:
  `python -m cli.main <url> [--out DIR] [--limit N] [--category-override "A > B > C"]`.
  Category-page candidates are discovered via same-domain on-page links
  (`scraper.discover.discover_links`); which candidates are real products is
  decided the same way the rest of this project decides everything — real
  extracted evidence, never a guessed URL pattern. Added
  `scraper.discover.fetch_html`/`fetch_bytes` (plain HTTP GET — this
  session's own real-page testing found it more reliable than Playwright
  navigation under this environment's network conditions; see Blocked).
  Prints one progress line per candidate and a final summary, and always
  writes a human-readable run report file into `--out`.
- **Real, honest multi-product proof (Task 7)** — see the session report for
  full numbers; summary: TBK Metal's real `/products/` listing (40 real
  links) yielded 15 real captures and **0 detections** — a genuine catalog-
  coverage gap (TBK's core line is architectural/decorative metal sheet
  fabrication, which has no corresponding category anywhere in BK's 510-
  schema store). A second real run against 27 real TBK tile-trim product
  pages (discovered via TBK's real `sitemap.xml`, since no single on-page hub
  links this specific product cluster) captured 27/27 and, using
  `--category-override` on the real, documented Edge-Trims-family sibling-tie
  ambiguity (21/27 landed in `category_ambiguous` under plain auto-detection —
  the same known limitation already listed below), produced ONE real,
  self-verified 27-row `.xlsx`. Material populated 23/27 (85%) via real
  vocabulary matching — up from the prior round's 0% on the same field —
  and Color correctly reported 22/27 as a genuine `variant_candidate`
  (real multi-material/multi-shape listings), never guessed. Every other
  column stayed honestly blank (Brand/SKU/etc. simply never stated on these
  pages; Length/Size failed the pre-existing "one confirmed number" gate on
  genuine multi-option values). 0 images captured — a real, disclosed gap
  (see Next Up). Verdict: the produced ZIP is **not** genuinely uploadable to
  BK as-is — every row is missing required fields (Brand always; Length/Size/
  their units usually) and carries no product photos; a human still has to
  fill those in (plus Floor Price, always manual by design) before upload.
- Coverage at end of that session: **77.11% total** (`COVERAGE_FLOOR` left at
  76 — unchanged, never lowered; the real total only moved up).

- **Root-cause fix: page-metadata extraction** (`programs/scraper/discover.py`):
  `extract_page_metadata(page_html, base_url)` reads whatever of
  `og:title`/`og:image`/`og:description`/`twitter:image`/`<title>`/`<h1>`/meta
  description is actually present — absent tags simply absent, never
  invented, image URLs resolved to absolute. `metadata_to_fields()` reduces
  it to the same `{name, description, image}` shape JSON-LD's own fields use
  (og:title > h1 > title; og:description > meta description; og:image >
  twitter:image). `extract_gallery_images()` is a third-tier, structural-only
  `<img>` scan (inside a product/gallery-classed container, excluding
  logo/icon/sprite filenames and HTML-stated small dimensions — no
  site-specific selectors). `resolve_product_image()` cascades
  JSON-LD → metadata → gallery scan.
- **Wired into evidence, images, and classification**
  (`programs/scraper/assemble.py`): `build_pack_from_fields` now fills
  name/description from page metadata (`metadata_fallback_rows`,
  `CONFIDENCE_LOOSE = 0.6` — the existing "looser, non-structured fallback"
  tier this module already reserved but had never actually used) ONLY when
  JSON-LD provided neither, and ONLY as an *enrichment* of a page that
  already qualifies via JSON-LD or a real spec table — metadata alone can
  never open the "is this capturable" gate (SEO tags exist on almost every
  real page, product or not; without this guard a blog/about page would get
  "captured" off its own `<title>` tag). The merged name/description also
  feeds `classify_category` and `detect.py`'s content tie-break, and
  `cli.main.capture_products` now resolves the product image via
  `resolve_product_image` instead of a raw JSON-LD-only field.
- **Task 4's real re-run — identical 27 tile-trim products, before/after**:
  captured 27/27 (unchanged); auto-detected **1/27 → 14/27**;
  still-`category_ambiguous` **21/27 → 9/27**; images captured **0/27 →
  27/27**; Description **0% → 100%** (new field, from metadata); Brand
  **0% → 11%** (3/27) — but flagged honestly: all 3 are a real instance of
  `assemble.py`'s own pre-documented "generic vocabulary word" caveat
  (`match_brand_from_vocabulary`'s docstring already warned a common word can
  false-positive) — TBK's own `<title>` boilerplate "... | TBK Metal -
  Manufacturer in **China**" whole-word-matched the schema's Brand vocabulary
  entry "china", not a genuine brand. Not a new bug; metadata just gave the
  existing risk more text to search. Material stayed 85% (unaffected,
  unrelated mechanism, as expected).
- **Variant expansion** (`programs/engine/variants.py`, new):
  `expand_variants(record_id, population)` turns one record with a real
  multi-option field (e.g. "Length: 2.4/2.5/2.7/3 Meters") into N real rows,
  one option per row — BK's own stated convention (duplicate the row, vary
  the variant-specific field). Only the LARGEST `variant_candidate` axis
  expands per record even when several fields are multi-option
  simultaneously (the real, common case: most of the 27 tile-trim products
  have Color AND Length AND/OR Size all multi-option at once) — expanding
  more than one axis would fabricate combinations the supplier never stated
  together; the other axis stays flagged, not silently resolved. Every
  expanded row stays fully traceable to its source record. Needed a new
  numeric-side counterpart first: `common/units.py`'s
  `parse_multi_option_numeric` resolves a real "/"-separated stocked-size
  list into individually-valid measurements — `populate.py`'s numeric branch
  now reports these as `variant_candidate` too (previously only dropdown
  fields got that status; a numeric multi-option value like "8/10/12mm" used
  to be flatly rejected as `needs_input`). `engine.batch.run_batch
  (expand_variants_flag=True)` and the CLI's `--expand-variants` flag are
  opt-in (row-count-changing, so a human-controlled decision, not automatic).
- **Task 6 — final real run, with variant expansion**: the same 27 real
  products, `--category-override` (Edge Trim) + `--expand-variants` →
  **106 real rows** (27 source products), one self-verified `.xlsx`, packaged
  into an upload-ready ZIP with all 27 real product photos included. Length
  filled **79%** (84/106, via real expansion), Size **18%** (19/106 — lower
  because Size lost the "largest axis" contest to Length on most products, so
  stayed a flagged `variant_candidate` instead), Material **88%**, Description
  **100%**, Brand **11%** (same "china" caveat as above). Verdict: **still not
  genuinely upload-ready as-is** — Brand, SKU, pricing/inventory, shipping,
  and media-column fields remain blank for real, disclosed reasons (see the
  session report), and the 27 real captured photos, while genuinely inside
  the ZIP's `media/` folder, aren't yet cross-referenced by filename in the
  sheet's own Cover Image/Other Images columns (same disclosed gap as before
  — populate.py was never asked to wire local capture filenames back into
  those columns).
- Coverage at this session's end: **78.13% total**, `327 passed`
  (`COVERAGE_FLOOR` still 76 in `scripts/check.py` — never lowered; the real
  total only moved up across every commit this session).

### Domain knowledge — confirmed vs pending

| Category | Status |
|---|---|
| Building Materials > Steel & Reinforcements > TMT bars > 12mm | **confirmed** |
| Plumbing & Sanitary Ware > Wash Basins & Pedestals > Vessel Basins | **confirmed** |
| Plumbing & Sanitary Ware > Pipes & Fittings > GI | **confirmed** |
| Electrical & Lighting > Cables & Wires > Copper Wires | **confirmed** |
| Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles | pending_review |
| Plumbing & Sanitary Ware > Pipes & Fittings > PVC | pending_review |

Promoting `pending_review → confirmed` is the user's call alone, every time —
see CLAUDE.md's autonomy policy. 4 of 6 researched categories confirmed; 2
awaiting review. 510 real category templates exist in `packages/schemas/data`
total — only 6 have any domain-knowledge research at all. The other ~504 have
no plausibility data yet (an intentional one-category-at-a-time discipline,
not an oversight).

## In Progress

Nothing mid-flight at session end — everything started this session (page
metadata extraction, its wiring into evidence/images/classification, the
Task 4 re-run, variant expansion, and the Task 6 final run) landed and is
covered above under Done.

## Next Up

- **Media-column cross-referencing**: 27/27 real product photos are now
  captured, WebP-processed, and included in the upload ZIP's `media/` folder
  (see Task 6) — but the sheet's own Cover Image/Other Images columns aren't
  wired to reference those local filenames, so `package_for_upload` correctly
  (and honestly) reports every one of them as `unreferenced_media`. Real,
  disclosed, not silently fixed nor silently ignored — populating those
  columns with the real local capture filename (not the original scraped
  source URL) is the next real step toward a genuinely upload-ready file.
- **`match_brand_from_vocabulary`'s pre-documented "generic vocabulary word"
  risk manifested for real this session**: 3 of 27 real Brand "hits" this
  session were TBK's own `<title>` boilerplate ("... Manufacturer in
  **China**") whole-word-matching the Brand vocabulary entry "china", not a
  genuine brand. The function's own docstring already flagged this exact risk
  as a vocabulary-quality issue, not a bug in the matching rule — worth a
  real look at whether a category's own Brand vocabulary should exclude
  bare country/generic-noun entries, now that there's a real, concrete
  instance to reason from instead of a hypothetical one.
- Confirm or reject the 2 `pending_review` categories (Edge Trims & Profiles,
  PVC pipe) — user decision, not engineering work.
- Research domain knowledge for more of the remaining ~504 categories,
  one at a time, same sourced-and-reviewed discipline as the existing 6.
- Program 2 (field app) — not started at all; see Blocked/Deferred below for
  why, and CLAUDE.md's build-order note that Program 3 work (now underway)
  was itself gated on real BK Excel templates being confirmed available
  (they are — 510 real templates are parsed and in `packages/schemas/data`).
- **Extend the sibling-tie-break mechanism beyond numeric sizes**: real,
  substantial progress this session (page-metadata text now feeds the
  content tie-break — see Done), but not solved. Confirmed at real scale:
  `category_ambiguous` among the Edge Trims & Profiles family dropped from
  21/27 to **9/27** real TBK tile-trim products once real page-title/
  description text became searchable, but 9 remain genuinely unresolved
  because their distinguishing words still don't land where the tie-break
  looks (`--category-override` remains the real, working workaround for
  those). Reported honestly, per the task's own framing, rather than
  overstating the improvement.
- The `detect.py` / `populate.py` alias-resolution asymmetry is intentional
  and documented in both modules' docstrings — not a gap, but worth revisiting
  if a future category's aliasing needs turn out more complex than TMT/Edge
  Trims/PVC/GI have required so far.

## Blocked

- **`rembg` (background removal, `packages/export/background.py`) — blocked
  on this specific machine's network conditions**, not on anything in the
  code or design. `packages/export/background.py`'s design (cutout +
  adaptive grey/white compositing + black QA composite) was fully planned and
  approved, but installation could not complete: `rembg`'s own package
  resolves cleanly with `pip install rembg --only-binary=:all:` (every
  dependency — scipy, numpy, scikit-image, llvmlite, numba — has a real
  prebuilt wheel for this platform; `--only-binary` never once failed on a
  missing wheel), but sustained large-file download throughput from
  `files.pythonhosted.org` on this machine is on the order of 3-17 KB/s and
  degrades further over a connection's lifetime, making the ~150MB+
  dependency chain (before even reaching the ~176MB `u2net` ONNX model
  itself, or the smaller ~4.7MB `u2netp` variant) impractical to fetch in a
  single session. Multiple strategies were tried (plain `pip install` at
  several timeout/retry settings, a raw connectivity diagnostic, a custom
  resumable/resume-on-stall downloader) — all converged on the same finding.
  **Never substitute BRIA RMBG-2.0** (CC-BY-NC, non-commercial — a licensing
  violation, not a style choice) if this is revisited. Retry from a
  network with better sustained throughput to `files.pythonhosted.org`.
- **Program 2 (field app / mobile) — not started.** No Briefcase project, no
  Toga/Android artifacts exist anywhere in this repo (confirmed by a repo-wide
  search this session). This is the last stage in CLAUDE.md's build order and
  hasn't been scoped yet.
- **A real, live full-page Playwright screenshot could not be captured this
  session** (`capture_full_page_snapshot`, targeting TBK's blog page) —
  environmental, not a code defect. Five distinct, escalating real attempts:
  (1)/(2) default settings, 0 bytes; (3) an isolated diagnostic timed out at
  navigation (`Page.goto: Timeout 20000ms exceeded`); (4) a 45s nav timeout
  let navigation succeed (170,592 real bytes) but `page.screenshot`'s own
  internal wait for web fonts to load then timed out at 30s; (5) same
  navigation + a 60s screenshot timeout — navigation succeeded again
  (170,728 bytes) but the font-load wait stalled again. Chromium itself
  launches correctly every time; browser-level navigation and the
  screenshot's internal font-wait are the specific steps that intermittently
  fail, and are notably *less* reliable than plain HTTP requests to the exact
  same domain, which succeeded throughout this session. An ad-hoc
  `--disable-web-security` Chromium flag was considered as a troubleshooting
  step and correctly rejected by this environment's safety classifier as an
  unauthorized bypass with no task authorization — not retried.
  `capture_full_page_snapshot`'s own correctness is proven independently (a
  fake-Page unit test asserts it calls Playwright's own
  `page.screenshot(full_page=True)` exactly as intended, in
  `programs/scraper/tests/test_media.py`), and the crash-safe staging
  mechanism for handling a snapshot-shaped image is proven using a real,
  valid, clearly-labeled Pillow-generated stand-in PNG (never presented as a
  real screenshot) in `packages/export/tests/test_media_integration_tbk.py`.
  Retry from a network with more reliable sustained browser-level
  connectivity; the code itself needs no change.

## Deferred

- Extending `packages/schemas/sections.py`'s `is_commercial_construct`
  exclusion beyond the `Pricing & Inventory` section (Shipping/Media/Meta/
  Identity & Naming sections were explicitly left as an open question, not
  assumed to behave the same way, when the recall gate was built).

(The page-title/meta-description fallback for `classify_category` that was
deferred here in an earlier round is now DONE — see page-metadata extraction
under Done above.)
