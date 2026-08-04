"""Researched, source-attributed domain knowledge for product categories.

A shared package (mirrors packages/schemas). It provides deterministic
plausibility flagging (check.py) over knowledge assembled from real web research
(research.py) and persisted to JSON (store.py). Every fact carries its source
URL, and nothing is trusted until a human moves it from pending_review to
confirmed. check_plausibility only flags a value — it never modifies or rejects.
"""

from .check import check_plausibility
from .models import CategoryKnowledge, PlausibleRange, Standard, TerminologyEntry
from .research import research_category

__all__ = [
    "CategoryKnowledge",
    "PlausibleRange",
    "Standard",
    "TerminologyEntry",
    "check_plausibility",
    "research_category",
]
