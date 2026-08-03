"""Discovery-layer tests. All fixture-based — no live network calls.

Each proves one guarantee of the "no evidence, no value" discipline applied to
scraping: real URLs only from a real sitemap, exactly the JSON-LD fields that
are present (nothing invented), an empty result when there is no structured
data, and that robots.txt is honored before anything is fetched.
"""

from pathlib import Path

from scraper import discover

FIX = Path(__file__).parent / "fixtures"


def _fix(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_fetch_sitemap_returns_real_urls_from_fixture():
    sitemap = _fix("sitemap.xml")

    def fake_get(url: str) -> str | None:
        # Only the /sitemap.xml candidate resolves; everything else is absent.
        return sitemap if url.endswith("/sitemap.xml") else None

    urls = discover.fetch_sitemap(
        "https://example.com", get_text=fake_get, robots_txt=""
    )
    assert urls == [
        "https://example.com/products/aluminum-tile-trim-1",
        "https://example.com/products/aluminum-tile-trim-2",
        "https://example.com/products/corner-profile-3",
    ]


def test_fetch_sitemap_returns_empty_when_no_sitemap():
    urls = discover.fetch_sitemap(
        "https://example.com", get_text=lambda url: None, robots_txt=""
    )
    assert urls == []


def test_extract_structured_data_returns_exactly_the_jsonld_fields():
    fields = discover.extract_structured_data(
        "https://example.com/p/1", html=_fix("product_jsonld.html")
    )
    assert fields == {
        "name": "Aluminum Tile Trim 10mm Silver",
        "sku": "ATT-10-SIL",
        "image": "https://example.com/img/att-10-sil.jpg",
        "description": "Anodised aluminum edge trim for 10mm tiles.",
        "brand": "Foshan Guanghong",
        "price": "2.35",
    }


def test_extract_structured_data_returns_empty_dict_when_no_structured_data():
    fields = discover.extract_structured_data(
        "https://example.com/p/2", html=_fix("product_nojsonld.html")
    )
    assert fields == {}


def test_robots_disallow_is_honored():
    url = "https://example.com/products/aluminum-tile-trim-1"
    assert discover.robots_allows(url, robots_txt=_fix("robots_disallow.txt")) is False


def test_robots_allows_when_not_disallowed():
    url = "https://example.com/catalog/item-1"
    assert discover.robots_allows(url, robots_txt=_fix("robots_disallow.txt")) is True
