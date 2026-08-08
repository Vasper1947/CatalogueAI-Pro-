"""fetch_html / fetch_bytes / discover_links: the CLI's plain-HTTP fetch
path and category-page link enumeration. Network calls are monkeypatched at
the same boundary the functions themselves use — no live network in tests."""

import urllib.request

from scraper import discover


def test_fetch_html_returns_decoded_text_on_success(monkeypatch):
    monkeypatch.setattr(discover, "_http_get", lambda url, timeout=15.0: "<html>hi</html>")
    assert discover.fetch_html("https://example.com") == "<html>hi</html>"


def test_fetch_html_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(discover, "_http_get", lambda url, timeout=15.0: None)
    assert discover.fetch_html("https://example.com") is None


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_bytes_returns_raw_bytes_on_success(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=15.0: _FakeResponse(b"\x89PNG\r\n")
    )
    assert discover.fetch_bytes("https://example.com/img.png") == b"\x89PNG\r\n"


def test_fetch_bytes_returns_none_on_failure(monkeypatch):
    def _raise(req, timeout=15.0):
        raise OSError("boom")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    assert discover.fetch_bytes("https://example.com/img.png") is None


def test_discover_links_finds_same_domain_links_only():
    html = """
    <html><body>
      <a href="/products/trim-1">Trim 1</a>
      <a href="https://example.com/products/trim-2">Trim 2</a>
      <a href="https://other-domain.com/products/trim-3">External</a>
    </body></html>
    """
    links = discover.discover_links(html, "https://example.com/category/edge-trims")
    assert links == [
        "https://example.com/products/trim-1",
        "https://example.com/products/trim-2",
    ]


def test_discover_links_excludes_mailto_tel_javascript_and_fragments():
    html = """
    <html><body>
      <a href="mailto:sales@example.com">Email</a>
      <a href="tel:+1234567890">Call</a>
      <a href="javascript:void(0)">JS</a>
      <a href="#section">Anchor</a>
      <a href="/products/real-one">Real</a>
    </body></html>
    """
    links = discover.discover_links(html, "https://example.com/category")
    assert links == ["https://example.com/products/real-one"]


def test_discover_links_deduplicates_and_excludes_self():
    html = """
    <html><body>
      <a href="/category">Self</a>
      <a href="/products/a">A</a>
      <a href="/products/a">A again</a>
      <a href="/products/a#reviews">A with fragment</a>
    </body></html>
    """
    links = discover.discover_links(html, "https://example.com/category")
    assert links == ["https://example.com/products/a"]


def test_discover_links_empty_when_no_anchors():
    assert discover.discover_links("<html><body>no links here</body></html>",
                                    "https://example.com/category") == []
