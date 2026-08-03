"""Persist parsed schemas to JSON on disk, with an index for lookup by category.

Layout under ``packages/schemas/data/``:
    <zip_category>/<filename_stem>.json   one file per template
    index.json                            category-path & product_type_id -> file

so any program can load "the schema for X" without re-parsing Excel.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _slug(text: str) -> str:
    """Filesystem-safe folder name, keeping it human-readable."""
    safe = "".join(ch if (ch.isalnum() or ch in " _-&()") else "_" for ch in text)
    return safe.strip() or "unknown"


def schema_path(schema, data_dir: Path | str = DATA_DIR) -> Path:
    stem = schema.filename
    if stem.lower().endswith(".xlsx"):
        stem = stem[:-5]
    return Path(data_dir) / _slug(schema.zip_category) / f"{stem}.json"


def write_schema(schema, data_dir: Path | str = DATA_DIR) -> Path:
    path = schema_path(schema, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def write_all(schemas, data_dir: Path | str = DATA_DIR) -> Path:
    """Write every schema plus an index.json; returns the index path."""
    data_dir = Path(data_dir)
    index: dict[str, dict] = {}
    for schema in schemas:
        path = write_schema(schema, data_dir)
        index[" > ".join(schema.category_path)] = {
            "file": path.relative_to(data_dir).as_posix(),
            "product_type_id": schema.category_ids.get("product_type_id"),
            "category_ids": schema.category_ids,
            "field_count": len(schema.fields),
            "writable_count": len(schema.writable_fields),
        }
    index_path = data_dir / "index.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return index_path


def load_index(data_dir: Path | str = DATA_DIR) -> dict:
    return json.loads((Path(data_dir) / "index.json").read_text(encoding="utf-8"))


def load_schema(category_key, data_dir: Path | str = DATA_DIR) -> dict:
    """Load a stored schema dict by category path (list or ' > '-joined string)."""
    data_dir = Path(data_dir)
    key = category_key if isinstance(category_key, str) else " > ".join(category_key)
    entry = load_index(data_dir).get(key)
    if entry is None:
        raise KeyError(f"no schema stored for {key!r}")
    return json.loads((data_dir / entry["file"]).read_text(encoding="utf-8"))
