"""BK-PACK interchange format — core spec constants.

A BK-PACK is a ZIP with exactly this at the root:
  datapackage.json      - manifest: version, producer, product count, media list
  evidence.jsonl         - one JSON row per product field (see evidence.py)
  manifest-sha256.txt    - "<sha256>  <path>" per payload file, for tamper detection
  media/                 - product images, named <sku>_1.<ext>, <sku>_2.<ext>, ...
"""

BKPACK_VERSION = "1.0"

REQUIRED_FILES = {
    "datapackage.json",
    "evidence.jsonl",
    "manifest-sha256.txt",
}

MEDIA_DIR = "media"
