"""Relocation regression check: units.py now lives in packages/common, and BOTH
programs that use it (scraper extraction + engine detection) must bind the exact
same normalize_value and get identical results from each call site.
"""

import common.units as common_units
from common.units import normalize_value as canonical
from engine.detect import normalize_value as engine_bound
from scraper.assemble import normalize_value as scraper_bound

_CASES = [
    "12 mm",
    "12mm",
    "2.5 m",
    "8/10/12mm",
    "300 x 600 mm",
    "1,5 cm",       # European decimal
    "1,234",        # ambiguous thousands vs decimal
    "12",           # unitless -> not assumed
    "Aluminum Alloy",  # categorical
    "",
]


def test_both_call_sites_bind_the_same_canonical_function():
    # No stale copy left behind under scraper.units.
    assert scraper_bound is common_units.normalize_value
    assert engine_bound is common_units.normalize_value
    assert scraper_bound is engine_bound is canonical


def test_identical_behavior_from_scraper_and_engine_call_sites():
    for raw in _CASES:
        assert scraper_bound(raw) == engine_bound(raw) == canonical(raw), raw


def test_scraper_units_module_is_gone():
    import importlib

    for dead in ("scraper.units",):
        try:
            importlib.import_module(dead)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{dead} should no longer exist after relocation")
