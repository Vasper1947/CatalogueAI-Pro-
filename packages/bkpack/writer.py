"""Assemble a BK-PACK ZIP from evidence rows and media files."""

import hashlib
import json
import zipfile
from pathlib import Path

from .spec import BKPACK_VERSION, MEDIA_DIR
from .evidence import EvidenceRow, write_evidence_jsonl


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_bkpack(
    output_path: str,
    evidence_rows: list[EvidenceRow],
    media_files: dict[str, bytes],
    producer: dict,
) -> None:
    """
    evidence_rows: every product field. Each row is already validated at
                   construction (EvidenceRow raises if it violates
                   'no evidence, no value'), so by the time this function
                   runs, coverage is already guaranteed — not re-checked
                   here, because it can't be false.
    media_files:   {"<sku>_1.webp": bytes, ...} — paths relative to media/.
    producer:      {"program": 1|2|3|4, "app_version": "...", "agent_id": "..."}
    """
    record_ids = sorted({r.record_id for r in evidence_rows})

    datapackage = {
        "bkpack_version": BKPACK_VERSION,
        "producer": producer,
        "product_count": len(record_ids),
        "resources": [{"path": f"{MEDIA_DIR}/{name}"} for name in sorted(media_files)],
        "provenance_policy": "no-evidence-no-value",
    }

    payload = {
        "datapackage.json": json.dumps(datapackage, indent=2).encode("utf-8"),
        "evidence.jsonl": write_evidence_jsonl(evidence_rows).encode("utf-8"),
    }
    for name, data in media_files.items():
        payload[f"{MEDIA_DIR}/{name}"] = data

    manifest = "".join(f"{_sha256(d)}  {p}\n" for p, d in sorted(payload.items()))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, d in payload.items():
            zf.writestr(p, d)
        zf.writestr("manifest-sha256.txt", manifest.encode("utf-8"))
