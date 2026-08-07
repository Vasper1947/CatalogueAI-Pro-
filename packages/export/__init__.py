"""BK Foundry — crash-safe staging, image processing, and CSV export.

Lives in packages/ (not programs/scraper/) because more than one program is
expected to need the same crash-safe staging convention (Program 4 likely
wants it too) — the same reasoning that moved units.py to packages/common/.

packages/bkpack stays untouched: this package adds files (a SKU.csv) alongside
a build_bkpack()-produced pack; it never modifies build_bkpack() or the
BK-PACK format itself.
"""
