"""Category classification by product TEXT content (name + description).

Complementary to detect.py's field-name matching (a separate signal, not wired
into Program 3 here): scores each schema by how many of the product's words
appear in that category's identifying vocabulary — category_path words, the
naming-convention literals (with [bracket] placeholders stripped), and the
breadcrumb. Plain word overlap only: no embeddings, no fuzzy matching.

When the top score is shared by more than one category_path, the suggestion
resolves to their longest common prefix (the family they agree on) rather than
an arbitrary tied leaf — a mechanical prefix comparison that does not change how
scores are computed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from schemas.store import DATA_DIR

CLASSIFY_THRESHOLD = 0.03  # named + tunable: below this, no suggestion is emitted

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "of", "in", "to", "by", "on",
    "is", "are", "be", "this", "that", "as", "at", "from", "it", "its", "you",
    "your", "can", "may", "will", "not", "no", "if", "then", "than", "which",
    "when", "where", "each", "per", "into", "these", "some", "any",
}

_BRACKET = re.compile(r"\[[^\]]*\]")
_NONWORD = re.compile(r"[^a-z0-9]+")


@dataclass
class Ranking:
    category_path: list
    score: float
    matched_terms: list


@dataclass
class Suggestion:
    category_path: list  # tie-resolved: full leaf, or longest common prefix if tied
    score: float
    matched_terms: list
    tied_count: int


def tokenize(text) -> set:
    """Lowercase word tokens, dropping stopwords and length-1 tokens."""
    return {
        w for w in _NONWORD.split(str(text).lower())
        if len(w) > 1 and w not in STOPWORDS
    }


def _strip_placeholders(naming) -> str:
    text = _BRACKET.sub(" ", str(naming or ""))
    return re.sub(r"(?i)pattern:", " ", text)


def schema_vocabulary(schema) -> set:
    """The words that identify a category: path + naming literals + breadcrumb."""
    instr = schema.get("instructions", {}) or {}
    parts = list(schema.get("category_path", []) or [])
    parts.append(_strip_placeholders(instr.get("naming_convention")))
    parts.append(instr.get("breadcrumb") or "")
    return tokenize(" ".join(parts))


def classify_category(product_text, schemas) -> list:
    """Rank every schema by word overlap with the product text (best first).

    Score = |product words ∩ category vocabulary| / |product words|. Each ranking
    carries the specific matched words so a human can see why it ranked.
    """
    product = tokenize(product_text)
    ranked = []
    for schema in schemas:
        matched = sorted(product & schema_vocabulary(schema))
        score = len(matched) / len(product) if product else 0.0
        ranked.append(
            Ranking(
                category_path=list(schema.get("category_path", []) or []),
                score=score,
                matched_terms=matched,
            )
        )
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


def _longest_common_prefix(paths: list) -> list:
    prefix: list = []
    for level in zip(*paths):
        if all(part == level[0] for part in level):
            prefix.append(level[0])
        else:
            break
    return prefix


def top_suggestion(ranked) -> Suggestion | None:
    """Resolve a ranking to a single suggestion.

    If more than one category_path shares the top score, the suggestion's path is
    their longest common prefix (the family they agree on); otherwise it is the
    single top leaf. Returns None if the ranking is empty or the top score is 0.
    """
    if not ranked or ranked[0].score <= 0:
        return None
    top_score = ranked[0].score
    tied = [r for r in ranked if r.score == top_score]
    if len(tied) == 1:
        return Suggestion(
            category_path=tied[0].category_path,
            score=top_score,
            matched_terms=tied[0].matched_terms,
            tied_count=1,
        )
    prefix = _longest_common_prefix([r.category_path for r in tied])
    matched = sorted(set().union(*(set(r.matched_terms) for r in tied)))
    return Suggestion(
        category_path=prefix, score=top_score, matched_terms=matched, tied_count=len(tied)
    )


def load_schemas(data_dir=DATA_DIR) -> list:
    """Load the parsed schema store (returns [] if it is absent)."""
    out = []
    for path in Path(data_dir).rglob("*.json"):
        if path.name == "index.json":
            continue
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out
