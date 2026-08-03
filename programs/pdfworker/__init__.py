"""Program 4 — the PDF worker.

This slice extracts text and embedded images from normal, born-digital PDFs,
detects (but does not fix) garbled-font pages, and assembles the trustworthy
content into a BK-PACK via packages/bkpack.

It never asserts text from a page flagged garbled, and never fabricates a value
a page does not actually provide.
"""
