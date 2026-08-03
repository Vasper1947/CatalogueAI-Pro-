"""Shared exception hierarchy for BK Foundry programs.

Every program (scraper, PDF worker, engine, field app) raises these instead
of bare exceptions, so a failure crosses program boundaries carrying a stable
machine-readable code and structured context — and the JSON logger can render
it uniformly without string-parsing a message.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all BK Foundry errors.

    Carries a short, stable ``code`` and an optional ``details`` mapping so a
    failure can be logged or serialised without parsing its message text.
    """

    code = "app_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}


class ValidationError(AppError):
    """Input or data violated a rule — e.g. a BK-PACK that breaks the ledger."""

    code = "validation_error"


class SourceError(AppError):
    """A source could not be reached or read: a web page, a PDF, an object store."""

    code = "source_error"


class ConfigError(AppError):
    """Required configuration is missing or invalid."""

    code = "config_error"
