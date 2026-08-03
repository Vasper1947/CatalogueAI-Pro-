"""
Run this: python demo.py

Builds a real BK-PACK from two fake tile products, validates it (passes),
then shows the ledger refusing to even construct a fabricated field.
"""

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from bkpack.validator import validate_bkpack

print("=== 1. Building a BK-PACK with real, sourced data ===")
rows = [
    EvidenceRow(
        record_id="TIL-001", field="colour", value="Statuario White",
        source_uri="pdf://goodwill_catalog.pdf#page=4", method="pdf", confidence=0.95,
    ),
    EvidenceRow(
        record_id="TIL-001", field="thickness_mm", value="9.5",
        source_uri="pdf://goodwill_catalog.pdf#page=4", method="pdf", confidence=0.9,
    ),
    EvidenceRow(
        record_id="TIL-001", field="slip_resistance", value=None,
        source_uri=None, method="pdf", confidence=1.0, absence=True,
    ),
    EvidenceRow(
        record_id="TIL-002", field="colour", value="Pearl Grey Marble",
        source_uri="pdf://goodwill_catalog.pdf#page=5", method="pdf", confidence=0.92,
    ),
]
build_bkpack(
    "sample.bkpack.zip",
    evidence_rows=rows,
    media_files={"TIL-001_1.webp": b"pretend-this-is-a-webp-image"},
    producer={"program": 4, "app_version": "0.1.0", "agent_id": "demo"},
)
print("Wrote sample.bkpack.zip\n")

print("=== 2. Validating it ===")
report = validate_bkpack("sample.bkpack.zip")
report.print_report()

print("\n=== 3. Trying to fabricate a value (this MUST fail) ===")
try:
    EvidenceRow(
        record_id="TIL-999", field="colour", value="Colour I Made Up",
        source_uri=None, method="pdf", confidence=0.99,
    )
    print("!! THIS SHOULD NOT PRINT — fabrication was not blocked !!")
except ValueError as e:
    print(f"Blocked, as designed:\n  {e}")
