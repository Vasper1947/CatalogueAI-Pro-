"""Persist researched CategoryKnowledge to JSON, with an index by category path.

Layout under ``packages/domain_knowledge/data/`` (same pattern as schemas' store):
    <slug>.json    one file per researched category
    index.json     category-path -> {file, review_status, researched_at}
"""

from __future__ import annotations

import json
from pathlib import Path

from domain_knowledge.models import CategoryKnowledge

DATA_DIR = Path(__file__).parent / "data"


def _slug(text: str) -> str:
    safe = "".join(ch if (ch.isalnum() or ch in " _-&()") else "_" for ch in text)
    return safe.strip() or "unknown"


def knowledge_path(category_path, data_dir: Path | str = DATA_DIR) -> Path:
    key = category_path if isinstance(category_path, str) else " - ".join(category_path)
    return Path(data_dir) / f"{_slug(key)}.json"


def _update_index(knowledge: CategoryKnowledge, data_dir: Path) -> None:
    index_path = data_dir / "index.json"
    index: dict = {}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    index[" > ".join(knowledge.category_path)] = {
        "file": knowledge_path(knowledge.category_path, data_dir).name,
        "review_status": knowledge.review_status,
        "researched_at": knowledge.researched_at,
    }
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def write_knowledge(knowledge: CategoryKnowledge, data_dir: Path | str = DATA_DIR) -> Path:
    data_dir = Path(data_dir)
    path = knowledge_path(knowledge.category_path, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(knowledge.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _update_index(knowledge, data_dir)
    return path


def load_knowledge(category_path, data_dir: Path | str = DATA_DIR) -> CategoryKnowledge:
    path = knowledge_path(category_path, data_dir)
    return CategoryKnowledge.from_dict(json.loads(path.read_text(encoding="utf-8")))
