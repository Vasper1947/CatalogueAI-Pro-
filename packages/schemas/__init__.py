"""BK bulk-upload template schema library.

Turns any BK bulk-upload .xlsx template (Template / Lookup / Instructions sheets)
into a structured TemplateSchema: fields with inferred types, required/locked
flags, dropdown vocabularies, category path and IDs, and the stated rules.

Shared infrastructure for all four programs — general enough that a new template
dropped in later parses with no code changes. See parser.py and store.py.
"""

from .models import Field, ParseFailure, ParseReport, TemplateSchema
from .parser import parse_all, parse_template, parse_zip

__all__ = [
    "Field",
    "ParseFailure",
    "ParseReport",
    "TemplateSchema",
    "parse_all",
    "parse_template",
    "parse_zip",
]
