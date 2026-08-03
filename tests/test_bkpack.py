"""
Tests for the BK-PACK core. Run with: pytest -q

Each test proves the ledger rejects one specific failure mode we built it
to catch — not just "does it run."
"""

import hashlib
import json
import zipfile

import pytest

from bkpack.evidence import EvidenceRow
from bkpack.writer import build_bkpack
from bkpack.reader import read_bkpack
from bkpack.validator import validate_bkpack


def _sample_evidence():
    return [
        EvidenceRow(
            record_id="TIL-001", field="colour", value="Statuario White",
            source_uri="pdf://catalog.pdf#page=4", method="pdf", confidence=0.95,
        ),
        EvidenceRow(
            record_id="TIL-001", field="thickness_mm", value="9.5",
            source_uri="pdf://catalog.pdf#page=4", method="pdf", confidence=0.9,
        ),
        EvidenceRow(
            record_id="TIL-001", field="slip_resistance", value=None,
            source_uri=None, method="pdf", confidence=1.0, absence=True,
        ),
        EvidenceRow(
            record_id="TIL-002", field="colour", value="Pearl Grey Marble",
            source_uri="pdf://catalog.pdf#page=5", method="pdf", confidence=0.92,
        ),
    ]


def test_roundtrip_valid_pack_passes(tmp_path):
    out = tmp_path / "test.bkpack.zip"
    build_bkpack(
        str(out),
        evidence_rows=_sample_evidence(),
        media_files={"TIL-001_1.webp": b"fake-image-bytes"},
        producer={"program": 4, "app_version": "0.1.0", "agent_id": "test"},
    )

    report = validate_bkpack(str(out))
    assert report.ok, report.errors

    data = read_bkpack(str(out))
    assert data["datapackage"]["product_count"] == 2
    values = {(r["record_id"], r["field"]): r["value"] for r in data["evidence"]}
    assert values[("TIL-001", "colour")] == "Statuario White"
    assert values[("TIL-001", "slip_resistance")] is None
    assert data["media"]["TIL-001_1.webp"] == b"fake-image-bytes"


def test_evidence_row_rejects_value_without_source():
    with pytest.raises(ValueError, match="no source_uri"):
        EvidenceRow(
            record_id="TIL-003", field="colour", value="Beige",
            source_uri=None, method="pdf", confidence=0.8,
        )


def test_evidence_row_rejects_absence_with_value():
    with pytest.raises(ValueError, match="absence=True"):
        EvidenceRow(
            record_id="TIL-003", field="colour", value="Beige",
            source_uri="pdf://x", method="pdf", confidence=0.8, absence=True,
        )


def test_evidence_row_rejects_silent_null():
    with pytest.raises(ValueError, match="not True"):
        EvidenceRow(
            record_id="TIL-003", field="colour", value=None,
            source_uri=None, method="pdf", confidence=0.8,
        )


def test_validator_catches_tampered_checksum(tmp_path):
    out = tmp_path / "good.zip"
    build_bkpack(
        str(out), evidence_rows=_sample_evidence(), media_files={},
        producer={"program": 4, "app_version": "0.1.0", "agent_id": "test"},
    )
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(out, "r") as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "datapackage.json":
                data = data.replace(b'"product_count": 2', b'"product_count": 999')
            dst.writestr(item, data)

    report = validate_bkpack(str(tampered))
    assert not report.ok
    assert any("checksum mismatch" in e for e in report.errors)


def test_validator_catches_missing_required_file(tmp_path):
    out = tmp_path / "good.zip"
    build_bkpack(
        str(out), evidence_rows=_sample_evidence(), media_files={},
        producer={"program": 4, "app_version": "0.1.0", "agent_id": "test"},
    )
    stripped = tmp_path / "stripped.zip"
    with zipfile.ZipFile(out, "r") as src, zipfile.ZipFile(stripped, "w") as dst:
        for item in src.infolist():
            if item.filename == "manifest-sha256.txt":
                continue
            dst.writestr(item, src.read(item.filename))

    report = validate_bkpack(str(stripped))
    assert not report.ok
    assert any("missing required file" in e for e in report.errors)


def test_validator_catches_hand_crafted_fabricated_value(tmp_path):
    """
    Proves the validator does NOT just trust the writer: even a ZIP built
    entirely by hand (bypassing EvidenceRow) is caught if a field carries
    a value with no source — the exact fabrication failure this ledger
    exists to prevent.
    """
    bad = tmp_path / "fabricated.zip"
    datapackage = {
        "bkpack_version": "1.0",
        "producer": {"program": 4, "app_version": "x", "agent_id": "x"},
        "product_count": 1,
        "resources": [],
        "provenance_policy": "no-evidence-no-value",
    }
    evidence_jsonl = json.dumps({
        "record_id": "FAKE-001", "field": "colour", "value": "Made Up Colour",
        "source_uri": None, "method": "pdf", "confidence": 0.99,
        "absence": False, "ts": 0,
    }) + "\n"

    payload = {
        "datapackage.json": json.dumps(datapackage).encode(),
        "evidence.jsonl": evidence_jsonl.encode(),
    }
    manifest = "".join(
        f"{hashlib.sha256(d).hexdigest()}  {p}\n" for p, d in sorted(payload.items())
    )
    with zipfile.ZipFile(bad, "w") as zf:
        for p, d in payload.items():
            zf.writestr(p, d)
        zf.writestr("manifest-sha256.txt", manifest.encode())

    report = validate_bkpack(str(bad))
    assert not report.ok
    assert any("no source_uri" in e for e in report.errors)
