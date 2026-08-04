"""Data model for researched, source-attributed domain knowledge.

Every fact carries the source URL it came from, and a freshly-researched
category always starts ``pending_review`` — nothing is trusted until a human
moves it to ``confirmed``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

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
    standards: list  # list[Standard]
    terminology: dict  # {synonym: TerminologyEntry}
    researched_at: str
    review_status: str = REVIEW_PENDING

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
        )
