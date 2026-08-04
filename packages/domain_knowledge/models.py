"""Data model for researched, source-attributed domain knowledge.

Every fact carries the source URL it came from, and a freshly-researched
category always starts ``pending_review`` — nothing is trusted until a human
moves it to ``confirmed``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

REVIEW_PENDING = "pending_review"
REVIEW_CONFIRMED = "confirmed"
REVIEW_REJECTED = "rejected"


@dataclass
class PlausibleRange:
    min: float
    max: float
    unit: str | None
    source_url: str


@dataclass
class Standard:
    """A named reference with a source. Used for two distinct kinds of fact:

    - ``standards``: a genuine governing/regulatory standard (e.g. IS 1786).
    - ``industry_references``: a real, sourced manufacturer spec or industry
      norm that is NOT a governing standard (e.g. a Schluter profile datasheet).

    Same shape, deliberately separated so a manufacturer's spec sheet is never
    presented as if it were a regulatory standard.
    """

    name: str
    description: str
    source_url: str


@dataclass
class TerminologyEntry:
    canonical_term: str
    source_url: str


@dataclass
class CategoryKnowledge:
    category_path: list
    plausible_ranges: dict  # {field_name: PlausibleRange}
    standards: list  # list[Standard] — genuine governing/regulatory standards
    terminology: dict  # {synonym: TerminologyEntry}
    researched_at: str
    review_status: str = REVIEW_PENDING
    # list[Standard] — real, sourced manufacturer specs / industry norms that are
    # NOT governing standards. Defaults to empty so pre-split data still loads.
    industry_references: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CategoryKnowledge:
        return cls(
            category_path=list(data.get("category_path", [])),
            plausible_ranges={
                name: PlausibleRange(**value)
                for name, value in (data.get("plausible_ranges") or {}).items()
            },
            standards=[Standard(**s) for s in (data.get("standards") or [])],
            terminology={
                syn: TerminologyEntry(**value)
                for syn, value in (data.get("terminology") or {}).items()
            },
            researched_at=data.get("researched_at", ""),
            review_status=data.get("review_status", REVIEW_PENDING),
            industry_references=[
                Standard(**s) for s in (data.get("industry_references") or [])
            ],
        )
