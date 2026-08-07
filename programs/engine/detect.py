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
class TieResolution:
    """How a genuine tie was broken by resolve_tie_by_content — reported for
    transparency: which word decided it, and which evidence field it came from."""

    method: str  # "content_tie_break"
    matched_word: str
    field: str


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
    # Set only on a tie-break winner resolved by resolve_tie_by_content.
    resolution: TieResolution | None = None
    # Set True on every member of a genuinely unresolved tied qualifying group
    # (see match_template) — never set alongside an accepted `best`. A caller
    # (e.g. programs/engine/app.py) uses this to report the ambiguity
    # explicitly instead of silently picking one.
    ambiguous_tie: bool = False


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
    schema field. recall — proportion of the schema's required (writable) fields
    that the evidence covers. Both feed the match decision (see match_template).
    """
    writable_canon = {canonical(n): n for n in _writable_names(schema)}
    available = set(writable_canon.values())  # this schema's own field names
    matched_count = 0
    matched_fields: list[str] = []
    for base_canon, value in evidence_map.items():
        target = base_canon
        if base_canon not in writable_canon:
            # Resolve field-name aliases toward THIS schema's own fields only
            # (aliases.py, e.g. Height -> Size). This is a CATEGORY-CONFIDENCE
            # signal: an alias is a reasoned judgment call (see aliases.py) that
            # this evidence conceptually corresponds to the schema field, which
            # is safe to credit toward matching/scoring even for an imprecise or
            # multi-option value (e.g. TBK Metal's "Height: 8/10/12mm"). It is
            # deliberately NOT applied when actually populating a value — see
            # engine/populate.py's populate_from_evidence, which requires an
            # exact canonical-name match before writing a customer-facing field.
            # Do not "fix" populate.py to match this; that would let an
            # approximate alias silently become a confirmed populated value.
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


_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(str(text))}


def _distinguishing_words(tied_candidates) -> dict[str, Candidate]:
    """word (lowercase) -> the single tied candidate it distinguishes.

    A word qualifies only if it is in a candidate's own LEAF segment
    (category_path[-1]) and is NOT: (a) also a word in the shared family
    prefix (category_path[:-1], exact whole-word match — e.g. singular "trim"
    survives even though the prefix has plural "trims"), or (b) shared with
    another tied candidate's leaf (e.g. "Profile" appearing in several
    siblings' leaf names distinguishes none of them).
    """
    if not tied_candidates:
        return {}
    prefix_words: set[str] = set()
    for cand in tied_candidates:
        prefix_words |= _words(" ".join(cand.category_path[:-1]))
    leaf_words = {
        id(cand): _words(cand.category_path[-1] if cand.category_path else "") - prefix_words
        for cand in tied_candidates
    }
    owners: dict[str, list] = {}
    for cand in tied_candidates:
        for w in leaf_words[id(cand)]:
            owners.setdefault(w, []).append(cand)
    return {w: cands[0] for w, cands in owners.items() if len(cands) == 1}


def resolve_tie_by_content(tied_candidates, evidence_map):
    """Break a genuine tie using each candidate's distinguishing leaf-name
    word(s) found in the product's evidence text — whole-word, case-insensitive,
    no fuzzy matching. Tried only after resolve_sibling_tie's numeric mechanism
    has failed (e.g. shape-named siblings, not sized ones).

    Searches every evidence value (not just a fixed 'name'/'description' field
    — a page may have neither, as the real TBK Metal case does) for each
    candidate's distinguishing words (see _distinguishing_words). Resolves only
    if the evidence text contains EXACTLY ONE such word across the whole tied
    group; zero or more than one leaves the tie genuinely, honestly unresolved.

    Returns (candidate | None, TieResolution | None).
    """
    distinguishing = _distinguishing_words(tied_candidates)
    if not distinguishing:
        return None, None
    found: list[tuple[str, str]] = []  # (word, field_name)
    for word in distinguishing:
        pattern = re.compile(r"(?i)\b" + re.escape(word) + r"\b")
        for field_name, value in evidence_map.items():
            if value is not None and pattern.search(str(value)):
                found.append((word, field_name))
                break  # one hit is enough to count this word as present
    if len(found) != 1:
        return None, None
    word, field_name = found[0]
    return distinguishing[word], TieResolution(
        method="content_tie_break", matched_word=word, field=field_name
    )


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

    A candidate QUALIFIES only if its precision clears MATCH_THRESHOLD *and* it
    clears the recall gate (_clears_recall_gate) — precision alone is not enough,
    because a wrong schema with a large field vocabulary can out-score the right
    one on precision through chance overlap while covering only a sliver of its
    own required fields (see RECALL_THRESHOLD's docstring). `best` is chosen from
    the QUALIFYING set's own top-precision tier, not the absolute top of all
    candidates — a schema that never qualifies (like the TBK case's top-precision
    tier) cannot decide anything, no matter how high its precision.

    If that top-qualifying tier has more than one member, it is a genuine tie:
    resolve_sibling_tie (numeric category-path size) is tried first, then
    resolve_tie_by_content (distinguishing leaf-name words in the evidence text).
    If resolved, the winner becomes `best` and is moved to candidates[0], with
    `.resolution` reporting how (content tie-breaks only). If NOT resolved,
    `best` stays None, `confidence` reports the tied precision (not a rejected
    higher tier's), and every tied candidate has `.ambiguous_tie = True` — this
    is never silently decided by file-load order or any other implicit pick; a
    caller (e.g. programs/engine/app.py) reports the ambiguity explicitly.

    Candidates are always sorted best-first BY PRECISION (aside from a resolved
    tie-break winner moved to the front) so a human can see what else was close.
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
    # Sort by precision only.
    scored.sort(key=lambda t: t[0].score, reverse=True)
    candidates = [c for c, _s in scored]

    qualifying = [(c, s) for c, s in scored if c.score >= MATCH_THRESHOLD and _clears_recall_gate(c)]
    if not qualifying:
        confidence = scored[0][0].score if scored else 0.0
        return None, confidence, candidates

    top_precision = qualifying[0][0].score
    tier = [(c, s) for c, s in qualifying if c.score == top_precision]

    if len(tier) == 1:
        cand, schema = tier[0]
        return schema, cand.score, candidates

    # Genuine tie within the qualifying set: try numeric, then content.
    tier_cands = [c for c, _s in tier]
    resolved = resolve_sibling_tie(tier_cands, evidence_map)
    resolution = None
    if resolved is None:
        resolved, resolution = resolve_tie_by_content(tier_cands, evidence_map)

    if resolved is not None:
        resolved.resolution = resolution  # None for numeric, TieResolution for content
        idx = next(i for i, c in enumerate(candidates) if c is resolved)
        candidates.insert(0, candidates.pop(idx))
        schema = next(s for c, s in tier if c is resolved)
        return schema, resolved.score, candidates

    # Genuinely unresolved: never an arbitrary pick — mark it explicitly.
    for c in tier_cands:
        c.ambiguous_tie = True
    return None, top_precision, candidates
