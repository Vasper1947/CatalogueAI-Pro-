"""BK-PACK — the ZIP interchange format binding BK's catalog automation programs."""

from .spec import BKPACK_VERSION
from .evidence import EvidenceRow
from .writer import build_bkpack
from .reader import read_bkpack
from .validator import validate_bkpack, ValidationReport

__all__ = [
    "BKPACK_VERSION",
    "EvidenceRow",
    "build_bkpack",
    "read_bkpack",
    "validate_bkpack",
    "ValidationReport",
]
