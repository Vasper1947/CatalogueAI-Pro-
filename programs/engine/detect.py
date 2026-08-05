"""Template detection: match a BK-PACK's evidence fields to a schema.

Matching is deliberately simple and auditable: case-insensitive whole-name
equivalence plus a tiny explicit synonym map. No substring or fuzzy matching —
a weak, honest score is better than a clever wrong guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from common.units import normalize_value
from schemas.aliases import resolve_field
from schemas.sections import is_commercial_construct

MATCH_THRESHOLD = 0.5  # named + tunable: below this there is no confident match

# A candidate must also cover a MAJORITY of its own required fields to be
# accepted — not just overlap superficially on precision. Grounded in the real
# TBK Metal Edge Trim page: precision alone picked "Decorative PVC Panels"
# (precision=0.625, but only 5 of its 18 required fields covered -> recall=
# 0.278) over the genuinely correct "Edge Trim" (precision=0.500, 4 of 7
# required fields covered -> recall=0.571) — a wrong, larger-vocabulary schema
# out-scored the right one on precision by chance overlap, and recall exposed
# it. Reuses MATCH_THRESHOLD's own "majority" bar for the second signal rather
# than a second, independently-tuned magic number.
RECALL_THRESHOLD = MATCH_THRESHOLD

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
    score: float  # precision: matched evidence fields / distinct evidence fields
    matched_fields: list
    # recall: required (writable) fields covered / required (writable) fields.
    # Reported for transparency; it does NOT drive the match decision (see
    # match_template). required_present / required_missing name the exact fields.
    recall: float = 0.0
    required_present: list = field(default_factory=list)
    required_missing: list = field(default_factory=list)


def _writable_names(schema) -> list[str]:
    return [f["name"] for f in writable_fields(schema)]


def _required_writable_names(schema) -> list[str]:
    """Required fields a human/evidence must supply: the schema's own ``required``
    flag intersected with writable fields. Locked/formula required fields auto-fill
    and can never be evidence-matched; Pricing & Inventory fields are BK selling
    constructs a supplier page never states (is_commercial_construct). Neither is
    counted as a recall gap."""
    return [
        f["name"]
        for f in writable_fields(schema)
        if f.get("required") and not is_commercial_construct(f)
    ]


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


def _score(evidence_map: dict, schema):
    """Return (precision, recall, matched_fields, required_present, required_missing).

    precision — proportion of distinct evidence fields that map to a writable
    schema field (unchanged; this is what the match decision uses).
    recall — proportion of the schema's required (writable) fields that the
    evidence covers. Reported only; it does not affect the decision.
    """
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
    precision = matched_count / len(evidence_map) if evidence_map else 0.0

    required = _required_writable_names(schema)
    matched_set = set(matched_fields)
    required_present = [r for r in required if r in matched_set]
    required_missing = [r for r in required if r not in matched_set]
    # Convention: a schema with no required fields has no recall denominator -> 0.0.
    recall = len(required_present) / len(required) if required else 0.0
    return precision, recall, matched_fields, required_present, required_missing


def _size_key(text):
    """Normalized (value, unit) if ``text`` is a single number+unit, else None."""
    value, unit, _conf = normalize_value(text)
    if isinstance(value, (int, float)) and unit is not None:
        return (value, unit)
    return None


def resolve_sibling_tie(tied_candidates, evidence):
    """Break a genuine top-precision tie by matching a size in the category path.

    For each tied candidate, take its category_path's final segment (e.g. "12mm")
    and normalize it via units.py. If exactly ONE tied candidate's segment is a
    number+unit that exactly equals some evidence value's normalized form in the
    same canonical unit, return that candidate. If zero or more than one match,
    return None — an unresolved tie stays honestly unresolved, never a forced pick.

    ``evidence`` may be the evidence map (field -> value) or any iterable of
    values; only the values are read. No fuzzy matching: equality is exact on the
    canonical-unit normalized number.
    """
    values = evidence.values() if isinstance(evidence, dict) else evidence
    evidence_sizes = set()
    for v in values:
        key = _size_key(v)
        if key is not None:
            evidence_sizes.add(key)
    if not evidence_sizes:
        return None
    matches = [
        cand
        for cand in tied_candidates
        if (_size_key(cand.category_path[-1]) if cand.category_path else None)
        in evidence_sizes
    ]
    return matches[0] if len(matches) == 1 else None


def _clears_recall_gate(cand: Candidate) -> bool:
    """True if recall doesn't disqualify this candidate from being accepted.

    A schema with no required-writable fields at all has no recall denominator
    (recall==0.0 by convention, see _score) — that is a "no data" state, not a
    failure, so the gate is inapplicable and precision alone governs (preserves
    prior behaviour for such schemas). A schema that DOES declare required
    fields must have recall clear RECALL_THRESHOLD to be accepted.
    """
    has_required_fields = bool(cand.required_present or cand.required_missing)
    return not has_required_fields or cand.recall >= RECALL_THRESHOLD


def match_template(bkpack_evidence, schemas):
    """Return (best_schema | None, confidence, all_candidates_scored).

    Score = proportion of the evidence's distinct candidate-attribute field names
    (see _is_candidate_attribute) that map to a schema writable field — directly,
    via canonicalization of decorated names ("<Diameter (mm)>" -> diameter), or
    via a category-aware field-name alias.

    A candidate is ACCEPTED as the match only if its precision clears
    MATCH_THRESHOLD *and* it clears the recall gate (_clears_recall_gate) —
    precision alone is not enough, because a wrong schema with a large field
    vocabulary can out-score the right one on precision through chance overlap
    while covering only a sliver of its own required fields (see RECALL_THRESHOLD's
    docstring for the real case this is grounded in). Candidates are always sorted
    best-first BY PRECISION (with a same-precision sibling tie-break, see
    resolve_sibling_tie) so a human can see what else was close — that order is
    unchanged. The accepted candidate is the FIRST in that order to also clear the
    recall gate, so a lower-precision-but-well-covered candidate can win over a
    higher-precision-but-shallow one; it is NOT always candidates[0].
    """
    evidence_map = _evidence_field_map(bkpack_evidence)
    # Each entry pairs a Candidate with its schema so a tie-break reorder keeps
    # the two in lockstep.
    scored = []
    for schema in schemas:
        precision, recall, matched, req_present, req_missing = _score(evidence_map, schema)
        cand = Candidate(
            category_path=schema.get("category_path", []),
            score=precision,
            matched_fields=matched,
            recall=recall,
            required_present=req_present,
            required_missing=req_missing,
        )
        scored.append((cand, schema))
    # Sort by precision only — the match decision is unchanged.
    scored.sort(key=lambda t: t[0].score, reverse=True)

    # Break a genuine tie at the top precision by value, when exactly one sibling
    # matches. Only reorders within the equal-precision group; the decision below
    # still runs on precision.
    if len(scored) > 1:
        top = scored[0][0].score
        tied_idx = [i for i, (c, _s) in enumerate(scored) if c.score == top]
        if len(tied_idx) > 1:
            resolved = resolve_sibling_tie([scored[i][0] for i in tied_idx], evidence_map)
            if resolved is not None and scored[0][0] is not resolved:
                j = next(i for i in tied_idx if scored[i][0] is resolved)
                scored.insert(0, scored.pop(j))

    candidates = [c for c, _s in scored]
    for cand, schema in scored:
        if cand.score < MATCH_THRESHOLD:
            break  # scored is precision-sorted descending; nothing further can qualify
        if _clears_recall_gate(cand):
            return schema, cand.score, candidates
    confidence = scored[0][0].score if scored else 0.0
    return None, confidence, candidates
