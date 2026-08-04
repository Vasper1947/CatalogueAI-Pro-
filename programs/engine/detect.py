"""Template detection: match a BK-PACK's evidence fields to a schema.

Matching is deliberately simple and auditable: case-insensitive whole-name
equivalence plus a tiny explicit synonym map. No substring or fuzzy matching —
a weak, honest score is better than a clever wrong guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from schemas.aliases import resolve_field

MATCH_THRESHOLD = 0.5  # named + tunable: below this there is no confident match

# Small, explicit synonym map (value = canonical form). Whole-name only.
SYNONYMS = {"title": "name", "cost": "price"}

# Fields the engine must NEVER score on or populate, regardless of evidence
# (canonical form). Defense-in-depth for the Floor Price manual-gate invariant:
# Floor Price is a business pricing decision with no source in extracted data,
# handled only by the fixed FLOOR_PRICE_NOTICE gate — never a populated value.
NEVER_POPULATE = {"floor price"}

# A trailing parenthetical that is ONLY a unit annotation carries no matching
# meaning: "Diameter (mm)" denotes the same field as "Diameter". A parenthetical
# that is not a unit — an index like "Dimensions (1)" — is part of the real field
# name and is preserved. (Real pages also wrap names as "<Grade>"; those angle
# brackets are extraction artefacts and are stripped too.)
_UNIT_PAREN_RE = re.compile(
    r"\s*\((?:mm|cm|m|meter|meters|metre|metres|in|inch|inches|ft|kg|g|mpa|%)\)\s*$",
    re.IGNORECASE,
)


def canonical(name: str) -> str:
    """Normalise a field name for comparison (lowercase, unify separators, synonyms)."""
    n = str(name).strip().lower()
    n = n.strip("<>").strip()  # drop extraction wrappers like <Grade>
    n = _UNIT_PAREN_RE.sub("", n).strip()  # drop a unit-only trailing parenthetical
    n = re.sub(r"[\s_\-]+", " ", n).strip()
    return SYNONYMS.get(n, n)


# The scraper appends its own content-based classification as a
# 'suggested_category' row (see programs/scraper/assemble.py). That is our own
# annotation, not a scraped product attribute — it must never inflate the
# denominator. This is our own field name, not a site-specific blocklist entry.
_ANNOTATION_FIELDS = {"suggested category"}
_URL_RE = re.compile(r"^\s*(?:https?://|www\.)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$")


def _is_candidate_attribute(name: str, value: object) -> bool:
    """Could this evidence field plausibly be a product spec attribute at all?

    A deterministic, explainable pre-filter — no ML, no fuzzy matching, no
    site-specific field-name blocklist. It removes only what is structurally not
    a spec attribute: our own 'suggested_category' annotation, and fields whose
    value is a bare URL or email (media / contact references). A genuine
    attribute is never dropped for being prose — Description is itself a schema
    field — so the filter keys off structure, not verbosity.
    """
    if canonical(name) in _ANNOTATION_FIELDS:
        return False
    text = "" if value is None else str(value)
    return not (_URL_RE.match(text) or _EMAIL_RE.match(text))


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


def _evidence_field_map(bkpack_evidence) -> dict[str, str]:
    """Distinct candidate-attribute evidence fields (canonical) -> a value.

    Fields that structurally cannot be a product spec attribute (our own
    'suggested_category' annotation, bare URL/email references) are excluded from
    BOTH numerator and denominator via _is_candidate_attribute — they never
    matched a schema field, they only inflated the denominator. The value is kept
    so field-name ALIASES that are only valid for certain value shapes (e.g.
    'Dimensions' -> Diameter only for a single length measure) can be resolved
    per-schema in _score.
    """
    seen: dict[str, str] = {}
    for row in bkpack_evidence:
        name = row.get("field")
        if not name:
            continue
        value = row.get("value")
        if not _is_candidate_attribute(name, value):
            continue
        c = canonical(name)
        if c not in seen:
            seen[c] = value
    return seen


def _score(evidence_map: dict, schema) -> tuple[float, list[str]]:
    writable_canon = {canonical(n): n for n in _writable_names(schema)}
    available = set(writable_canon.values())  # this schema's own field names
    matched_count = 0
    matched_fields: list[str] = []
    for base_canon, value in evidence_map.items():
        target = base_canon
        if base_canon not in writable_canon:
            # Resolve field-name aliases toward THIS schema's own fields only.
            target = canonical(resolve_field(base_canon, value, available_fields=available))
        if target in writable_canon:
            matched_count += 1
            field_name = writable_canon[target]
            if field_name not in matched_fields:
                matched_fields.append(field_name)
    score = matched_count / len(evidence_map) if evidence_map else 0.0
    return score, matched_fields


def match_template(bkpack_evidence, schemas):
    """Return (best_schema | None, confidence, all_candidates_scored).

    Score = proportion of the evidence's distinct candidate-attribute field names
    (see _is_candidate_attribute) that map to a schema writable field — directly,
    via canonicalization of decorated names ("<Diameter (mm)>" -> diameter), or
    via a category-aware field-name alias. The best schema is returned only if its
    score meets MATCH_THRESHOLD; otherwise None (with the sub-threshold
    confidence). All candidates are always returned, sorted best-first, so a human
    can see what else was close.
    """
    evidence_map = _evidence_field_map(bkpack_evidence)
    scored = []
    for schema in schemas:
        score, matched = _score(evidence_map, schema)
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
