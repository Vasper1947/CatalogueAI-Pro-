"""Discovery layer: find product URLs and read structured data from a page.

Two layers in this slice:
  * ``fetch_sitemap`` enumerates product URLs from sitemap.xml (and any sitemap
    referenced in robots.txt). It never guesses URLs — no sitemap means [].
  * ``extract_structured_data`` reads schema.org/Product JSON-LD from a page and
    returns only the fields actually present. It never fabricates a field.

robots.txt is consulted via ``robots_allows`` before any live fetch; a
disallowed URL is refused by the caller, not fetched.

Every function that touches the network accepts an injected source (``get_text``
/ ``robots_txt`` / ``html``) so the automated tests run entirely on fixtures.
"""

from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

USER_AGENT = "BKFoundryScraper/0.1 (+https://github.com/Vasper1947/CatalogueAI-Pro-)"


def _http_get(url: str, *, timeout: float = 15.0) -> str | None:
    """Fetch text over HTTP with our UA. Returns None on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
        return None


def fetch_html(url: str, *, timeout: float = 15.0) -> str | None:
    """Plain HTTP GET for page markup — the fast, reliable path for a
    static-HTML page (this project's own real-page testing found it
    consistently more reliable than Playwright's browser-level navigation
    under this environment's network conditions; see ROADMAP.md's Blocked
    section). Returns None on any failure; never raises. A caller that needs
    JS-rendered markup can still fall back to extract_structured_data's own
    Playwright rendering by passing html=None."""
    return _http_get(url, timeout=timeout)


def fetch_bytes(url: str, *, timeout: float = 15.0) -> bytes | None:
    """Plain HTTP GET for binary content (a product photo, a media file) —
    same reasoning as fetch_html, but the raw, undecoded bytes. Returns None
    on any failure; never raises, never fabricates placeholder bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
        return None


_SKIP_LINK_RE = re.compile(r"(?i)^(mailto:|tel:|javascript:|#)")


def discover_links(page_html: str, base_url: str) -> list[str]:
    """Same-domain, absolute, deduplicated links found on a page — a general
    candidate list for a category/listing page's product links. Does not
    itself decide which candidates are product pages (a caller probes each
    the same way it would probe any page: does it actually have usable
    evidence?); a page with no same-domain anchor links yields []. The page's
    own URL (fragment-stripped) is excluded so it never candidates itself."""
    soup = BeautifulSoup(page_html or "", "html.parser")
    base_host = urlparse(base_url).netloc
    self_url = base_url.split("#", 1)[0]
    seen: set[str] = set()
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"]).strip()
        if not href or _SKIP_LINK_RE.match(href):
            continue
        resolved = urljoin(base_url, href).split("#", 1)[0]
        if urlparse(resolved).netloc != base_host or resolved == self_url:
            continue
        if resolved not in seen:
            seen.add(resolved)
            links.append(resolved)
    return links


def _get_robots(
    base_url: str, *, robots_txt: str | None = None
) -> urllib.robotparser.RobotFileParser:
    """Return a parsed robots.txt for base_url's domain.

    If ``robots_txt`` is supplied (a fixture) it is parsed directly with no
    network call. A missing/unreachable robots.txt is treated as allow-all,
    per the robots convention.
    """
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    if robots_txt is None:
        robots_txt = _http_get(robots_url)
    rp.parse(robots_txt.splitlines() if robots_txt else [])
    return rp


def robots_allows(page_url: str, *, robots_txt: str | None = None) -> bool:
    """True if our user agent may fetch page_url according to robots.txt."""
    rp = _get_robots(page_url, robots_txt=robots_txt)
    return rp.can_fetch(USER_AGENT, page_url)


def _sitemaps_from_robots(base_url: str, *, robots_txt: str | None = None) -> list[str]:
    rp = _get_robots(base_url, robots_txt=robots_txt)
    maps = rp.site_maps()
    return list(maps) if maps else []


def _local_name(tag: str) -> str:
    """The tag name without its XML namespace, e.g. '{ns}loc' -> 'loc'."""
    return tag.rsplit("}", 1)[-1]


def _parse_sitemap(xml_text: str) -> tuple[str, list[str]]:
    """Parse a sitemap document.

    Returns ``(kind, locs)`` where kind is 'index' (locs point at child
    sitemaps) or 'urlset' (locs are page URLs). Unparseable input -> empty.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ("urlset", [])
    kind = "index" if _local_name(root.tag) == "sitemapindex" else "urlset"
    locs = [
        node.text.strip()
        for node in root.iter()
        if _local_name(node.tag) == "loc" and node.text and node.text.strip()
    ]
    return (kind, locs)


def fetch_sitemap(
    base_url: str,
    *,
    get_text: Callable[[str], str | None] | None = None,
    robots_txt: str | None = None,
) -> list[str]:
    """Return product-page URLs discovered from the site's sitemap(s).

    Checks ``/sitemap.xml`` plus any ``Sitemap:`` entries in robots.txt, and
    follows a sitemap index one level down to its child sitemaps. Returns [] if
    no sitemap is found — it never guesses at URLs.

    ``get_text(url) -> str | None`` is injected so tests supply fixtures rather
    than making live calls; it defaults to a real HTTP GET.
    """
    if get_text is None:
        get_text = _http_get

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [f"{root}/sitemap.xml", *_sitemaps_from_robots(base_url, robots_txt=robots_txt)]

    seen: set[str] = set()
    urls: list[str] = []

    def _add(url: str) -> None:
        if url not in seen:
            seen.add(url)
            urls.append(url)

    for sitemap_url in candidates:
        text = get_text(sitemap_url)
        if not text:
            continue
        kind, locs = _parse_sitemap(text)
        if kind == "index":
            for child_url in locs:
                child_text = get_text(child_url)
                if not child_text:
                    continue
                _, child_locs = _parse_sitemap(child_text)
                for url in child_locs:
                    _add(url)
        else:
            for url in locs:
                _add(url)

    return urls


def _first_image(value: object) -> str | None:
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        found = value.get("url") or value.get("contentUrl")
        return found if isinstance(found, str) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _brand_name(value: object) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
    if isinstance(value, list) and value:
        return _brand_name(value[0])
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _offer_price(value: object) -> str | None:
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        price = value.get("price")
        if price is None and isinstance(value.get("priceSpecification"), dict):
            price = value["priceSpecification"].get("price")
        if price is not None and str(price).strip():
            return str(price).strip()
    return None


def _product_fields(node: dict) -> dict:
    """Pull the known schema.org/Product fields that are present on one node.

    A field only appears in the result if it is actually present with a value —
    an absent field is omitted, never guessed.
    """
    fields: dict[str, str] = {}
    name = node.get("name")
    if isinstance(name, str) and name.strip():
        fields["name"] = name.strip()
    sku = node.get("sku")
    if sku is not None and str(sku).strip():
        fields["sku"] = str(sku).strip()
    image = _first_image(node.get("image"))
    if image:
        fields["image"] = image
    description = node.get("description")
    if isinstance(description, str) and description.strip():
        fields["description"] = description.strip()
    brand = _brand_name(node.get("brand"))
    if brand:
        fields["brand"] = brand
    price = _offer_price(node.get("offers"))
    if price:
        fields["price"] = price
    return fields


def _is_product_type(type_value: object) -> bool:
    if isinstance(type_value, str):
        return type_value.split("/")[-1] == "Product"
    if isinstance(type_value, list):
        return any(_is_product_type(t) for t in type_value)
    return False


def _find_products(data: object) -> Iterator[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _find_products(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _find_products(data["@graph"])
        if _is_product_type(data.get("@type")):
            yield data


def _iter_jsonld_products(html: str) -> Iterator[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        yield from _find_products(data)


def _render_html(page_url: str) -> str | None:
    """Render page_url with headless Chromium and return its HTML.

    Imported lazily so the module (and its fixture-based tests) do not require
    Playwright to be installed.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            html = page.content()
            browser.close()
            return html
    except (PlaywrightError, OSError):
        return None


def extract_structured_data(page_url: str, *, html: str | None = None) -> dict:
    """Return the schema.org/Product fields found in page_url's JSON-LD.

    ``html`` supplies the page markup directly (tests use a fixture); otherwise
    the page is rendered with Playwright so JS-built markup is included. Returns
    only fields actually present — an absent field is omitted, never guessed. An
    empty dict means no usable structured data was found.
    """
    if html is None:
        html = _render_html(page_url)
    if not html:
        return {}
    for node in _iter_jsonld_products(html):
        fields = _product_fields(node)
        if fields:
            return fields
    return {}


_GIF_RE = re.compile(r"\.gif(?:[?#].*)?$", re.IGNORECASE)


def find_media(page_html: str, base_url: str) -> list[dict]:
    """Return [{"url", "media_type"}] for <video>/<source> elements and .gif
    references on the page. Relative URLs are resolved against base_url.
    Deduplicated by resolved URL. Empty list if the page has neither —
    never guessed, never invented.
    """
    soup = BeautifulSoup(page_html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()

    def _add(raw_url, media_type: str) -> None:
        if not raw_url or not str(raw_url).strip():
            return
        resolved = urljoin(base_url, str(raw_url).strip())
        if resolved not in seen:
            seen.add(resolved)
            results.append({"url": resolved, "media_type": media_type})

    for video in soup.find_all("video"):
        _add(video.get("src"), "video")
        for source in video.find_all("source"):
            _add(source.get("src"), "video")

    for tag in soup.find_all(["img", "a", "source"]):
        src = tag.get("src") or tag.get("href") or tag.get("data-src")
        if src and _GIF_RE.search(str(src)):
            _add(src, "gif")

    return results


def capture_full_page_snapshot(page) -> bytes:
    """Full-page PNG screenshot of an already-loaded Playwright page, via
    Playwright's own page.screenshot(full_page=True) -- no custom capture
    logic, just the existing capability."""
    return page.screenshot(full_page=True)


def render_and_snapshot(page_url: str) -> tuple[str | None, bytes | None]:
    """Render page_url with headless Chromium and return (html, snapshot_png)
    from the SAME browser session -- so the snapshot reflects exactly the page
    extract_structured_data/find_media would see. Either element is None on
    failure (imported lazily, same reasoning as _render_html)."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            html = page.content()
            snapshot = capture_full_page_snapshot(page)
            browser.close()
            return html, snapshot
    except (PlaywrightError, OSError):
        return None, None


def extract_spec_table(page_html: str) -> list[tuple[str, str]]:
    """Extract (key, value) spec pairs from two-column tables and definition lists.

    Only the clear two-column key/value shape is trusted:
      * ``<table>`` rows with exactly two cells (``<th>``/``<td>``), and
      * ``<dl>`` definition lists (``<dt>`` paired with its following ``<dd>``s).

    Wide/data tables, single-cell rows, and bespoke non-table spec widgets
    (arbitrary ``<div>`` layouts, JS-rendered widgets) are out of scope — a page
    with no table/dl structure yields an empty list, never a guessed parse.
    """
    soup = BeautifulSoup(page_html or "", "html.parser")
    pairs: list[tuple[str, str]] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) != 2:
                continue
            key = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)
            if key and value:
                pairs.append((key, value))

    for dl in soup.find_all("dl"):
        current_key: str | None = None
        for child in dl.find_all(["dt", "dd"]):
            if child.name == "dt":
                current_key = child.get_text(" ", strip=True) or None
            else:  # dd
                value = child.get_text(" ", strip=True)
                if current_key and value:
                    pairs.append((current_key, value))

    return pairs
