"""Data model for a parsed BK template schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Field:
    """One column of the Template sheet."""

    name: str
    column: str  # column letter, e.g. "A"
    type: str  # "string" | "numeric" | "dropdown"
    required: bool = False
    conditional: bool = False
    locked: bool = False
    is_formula: bool = False
    section: str | None = None
    dropdown_source: str | None = None  # "inline" | "lookup:<ColumnName>"
    vocabulary: list[str] = field(default_factory=list)


@dataclass
class TemplateSchema:
    """The full parsed schema for one template file."""

    zip_category: str
    filename: str
    category_path: list[str]  # 1-4 levels, top category first
    category_ids: dict  # {category_id, subcategory_id, sub_subcategory_id, product_type_id}
    fields: list[Field]
    lookups: dict  # {lookup_name: [values]}
    instructions: dict  # {breadcrumb, naming_convention, row_limit, media_options, ...}

    @property
    def writable_fields(self) -> list[Field]:
        """Fields a user actually fills in — locked and formula columns excluded."""
        return [f for f in self.fields if not (f.locked or f.is_formula)]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["writable_fields"] = [f.name for f in self.writable_fields]
        return data


@dataclass
class ParseFailure:
    """A file that could not be parsed cleanly, with the specific reason."""

    source: str  # "<zip>::<filename>"
    reason: str


@dataclass
class ParseReport:
    """Result of a full folder run: every schema plus every failure."""

    schemas: list  # list[TemplateSchema]
    failures: list  # list[ParseFailure]
    files_found: int
