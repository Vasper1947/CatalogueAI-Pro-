"""Program 1 — the catalog scraper.

This slice covers the first two discovery layers only: enumerating product
pages from sitemap.xml and reading schema.org/Product JSON-LD off each page,
then assembling the found fields into a BK-PACK via packages/bkpack.

It never fabricates a field that structured data doesn't provide, and never
fetches anything robots.txt disallows.
"""
