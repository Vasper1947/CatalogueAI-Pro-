"""Match a raw evidence value to a dropdown field's real, controlled
vocabulary — deterministic, auditable, strictest-first. No fuzzy matching, no
edit-distance, no embeddings: every level here is exact string comparison
after a named, inspectable transformation, so a match (or a refusal to match)
can always be explained by which level produced it.

    match_to_vocabulary(raw_value, vocabulary) -> (matched_term | None, method, confidence)

Levels, tried in order, stopping at the first that produces a determinate
result (see below):
    1. exact                  — byte-for-byte equality
    2. case_insensitive       — equal ignoring case
    3. normalized             — equal after punctuation/whitespace
                                 normalization and a small set of known
                                 British/American spelling equivalences
                                 (Aluminum/Aluminium, Colour/Color, Grey/Gray)
    4. whole_word_containment — the raw value contains exactly one
                                 vocabulary term as a complete word (or
                                 word-sequence for multi-word terms), e.g.
                                 "Aluminum Alloy" -> "Aluminium"

At each level: zero matches moves on to the next level; exactly one match
returns immediately (strictest-first, stop at first hit); two or more matches
AT THAT LEVEL is a genuine ambiguity — not resolved by falling through to a
weaker level — and returns (None, "<level>_ambiguous", 0.0). Zero matches at
every level returns (None, "no_match", 0.0). Every outcome reports which
level produced it, for auditability downstream.
"""

from __future__ import annotations

import re

EXACT = 1.0
CASE_INSENSITIVE = 0.95
NORMALIZED = 0.85
WHOLE_WORD_CONTAINMENT = 0.7
NO_MATCH = 0.0

# Known British/American (or otherwise equivalent) spelling pairs that must
# resolve to the same normalized token. Not a general spell-checker or
# synonym engine — a small, explicit, inspectable list, the same discipline
# schemas/aliases.py already applies to field-name synonyms.
_SPELLING_EQUIVALENCES = [
    {"aluminum", "aluminium"},
    {"color", "colour"},
    {"gray", "grey"},
]
_SPELLING_CANON: dict[str, str] = {}
for _group in _SPELLING_EQUIVALENCES:
    _representative = min(_group)
    for _word in _group:
        _SPELLING_CANON[_word] = _representative


def _normalize_tokens(text: str) -> list[str]:
    """Lowercase, strip punctuation to whitespace, collapse whitespace, and
    canonicalize known spelling variants — word by word."""
    lowered = re.sub(r"[^a-z0-9]+", " ", str(text).lower())
    return [_SPELLING_CANON.get(w, w) for w in lowered.split()]


def _normalize(text: str) -> str:
    return " ".join(_normalize_tokens(text))


def _contains_whole_word(raw_tokens: list[str], term_tokens: list[str]) -> bool:
    """True if term_tokens appears as a contiguous run within raw_tokens."""
    if not term_tokens or not raw_tokens or len(term_tokens) > len(raw_tokens):
        return False
    n = len(term_tokens)
    return any(
        raw_tokens[i : i + n] == term_tokens
        for i in range(len(raw_tokens) - n + 1)
    )


def find_whole_word_matches(raw_value, vocabulary: list[str]) -> list[str]:
    """Every vocabulary term present in raw_value as a complete word (or
    word-sequence), in vocabulary order, deduplicated. Public so callers that
    need the FULL candidate set on ambiguity (e.g. populate.py's
    variant_candidate reporting for a multi-option value like
    "Silver/Golden/Bronze") don't have to reimplement this matching logic —
    match_to_vocabulary's own whole_word_containment level is built on it."""
    raw = str(raw_value or "")
    if not raw.strip() or not vocabulary:
        return []
    raw_tokens = _normalize_tokens(raw)
    matches: list[str] = []
    seen: set[str] = set()
    for term in vocabulary:
        if term in seen:
            continue
        term_tokens = _normalize_tokens(term)
        if term_tokens and _contains_whole_word(raw_tokens, term_tokens):
            matches.append(term)
            seen.add(term)
    return matches


def match_to_vocabulary(raw_value, vocabulary: list[str]) -> tuple[str | None, str, float]:
    """Match raw_value against vocabulary, strictest method first. See module
    docstring for the four levels and the ambiguity rule."""
    raw = str(raw_value) if raw_value is not None else ""
    if not raw.strip() or not vocabulary:
        return None, "no_match", NO_MATCH

    exact_hits = [t for t in vocabulary if raw == t]
    if len(exact_hits) == 1:
        return exact_hits[0], "exact", EXACT
    if len(exact_hits) > 1:
        return None, "exact_ambiguous", NO_MATCH

    ci_hits = [t for t in vocabulary if raw.lower() == t.lower()]
    if len(ci_hits) == 1:
        return ci_hits[0], "case_insensitive", CASE_INSENSITIVE
    if len(ci_hits) > 1:
        return None, "case_insensitive_ambiguous", NO_MATCH

    raw_norm = _normalize(raw)
    norm_hits = [t for t in vocabulary if raw_norm and raw_norm == _normalize(t)]
    if len(norm_hits) == 1:
        return norm_hits[0], "normalized", NORMALIZED
    if len(norm_hits) > 1:
        return None, "normalized_ambiguous", NO_MATCH

    containment_hits = find_whole_word_matches(raw, vocabulary)
    if len(containment_hits) == 1:
        return containment_hits[0], "whole_word_containment", WHOLE_WORD_CONTAINMENT
    if len(containment_hits) > 1:
        return None, "whole_word_containment_ambiguous", NO_MATCH

    return None, "no_match", NO_MATCH
