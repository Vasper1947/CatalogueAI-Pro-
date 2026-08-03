"""Template detection: match a BK-PACK's evidence fields to a schema.

Matching is deliberately simple and auditable: case-insensitive whole-name
equivalence plus a tiny explicit synonym map. No substring or fuzzy matching —
a weak, honest score is better than a clever wrong guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MATCH_THRESHOLD = 0.5  # named + tunable: below this there is no confident match

# Small, explicit synonym map (value = canonical form). Whole-name only.
SYNONYMS = {"title": "name", "cost": "price"}

# Fields the engine must NEVER score on or populate, regardless of evidence
# (canonical form). Defense-in-depth for the Floor Price manual-gate invariant:
# Floor Price is a business pricing decision with no source in extracted data,
# handled only by the fixed FLOOR_PRICE_NOTICE gate — never a populated value.
NEVER_POPULATE = {"floor price"}


def canonical(name: str) -> str:
    """Normalise a field name for comparison (lowercase, unify separators, synonyms)."""
    n = re.sub(r"[\s_\-]+", " ", str(name).strip().lower())
    return SYNONYMS.get(n, n)


def writable_fields(schema) -> list:
    """A schema's user-fillable fields: not locked, not formula, not never-populate."""
    return [
        f
        for f in schema.get("fields", [])
        if not (f.get("locked") or f.get("is_formula"))
        and canonical(f.get("name", "")) not in NEVER_POPULATE
    ]


@dataclass
class Candidate:
    category_path: list
    score: float
    matched_fields: list


def _writable_names(schema) -> list[str]:
    return [f["name"] for f in writable_fields(schema)]


def _evidence_field_names(bkpack_evidence) -> list[str]:
    """Distinct evidence field names, deduped by canonical form (original kept)."""
    seen: dict[str, str] = {}
    for row in bkpack_evidence:
        name = row.get("field")
        if name:
            seen.setdefault(canonical(name), name)
    return list(seen.values())


def _score(evidence_canon: set[str], schema) -> tuple[float, list[str]]:
    writable_canon = {canonical(n): n for n in _writable_names(schema)}
    matched = [writable_canon[c] for c in evidence_canon if c in writable_canon]
    score = len(matched) / len(evidence_canon) if evidence_canon else 0.0
    return score, matched


def match_template(bkpack_evidence, schemas):
    """Return (best_schema | None, confidence, all_candidates_scored).

    Score = proportion of the evidence's distinct field names that map to a
    schema writable field. The best schema is returned only if its score meets
    MATCH_THRESHOLD; otherwise None (with the sub-threshold confidence). All
    candidates are always returned, sorted best-first, so a human can see what
    else was close.
    """
    evidence_canon = {canonical(n) for n in _evidence_field_names(bkpack_evidence)}
    scored = []
    for schema in schemas:
        score, matched = _score(evidence_canon, schema)
        scored.append((schema, score, matched))
    scored.sort(key=lambda t: t[1], reverse=True)

    candidates = [
        Candidate(category_path=s.get("category_path", []), score=sc, matched_fields=m)
        for s, sc, m in scored
    ]
    if scored and scored[0][1] >= MATCH_THRESHOLD:
        best_schema, best_score, _ = scored[0]
        return best_schema, best_score, candidates
    confidence = scored[0][1] if scored else 0.0
    return None, confidence, candidates
