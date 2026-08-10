"""extract_page_metadata / metadata_to_fields / extract_gallery_images /
resolve_product_image: the page-metadata fallback layer that fires
regardless of JSON-LD and never overrides it when both are present."""

from scraper.discover import (
    extract_gallery_images,
    extract_page_metadata,
    metadata_to_fields,
    resolve_product_image,
)

BASE = "https://example.com/products/widget"


def test_extracts_all_present_tags():
    html = """
    <html><head>
      <title>Widget Pro | Example Co</title>
      <meta property="og:title" content="Widget Pro">
      <meta property="og:description" content="A great widget.">
      <meta property="og:image" content="/img/widget.jpg">
      <meta name="twitter:image" content="/img/widget-tw.jpg">
      <meta name="description" content="The generic meta description.">
    </head><body><h1>Widget Pro Heading</h1></body></html>
    """
    meta = extract_page_metadata(html, BASE)
    assert meta == {
        "og:title": "Widget Pro",
        "og:description": "A great widget.",
        "og:image": "https://example.com/img/widget.jpg",
        "twitter:image": "https://example.com/img/widget-tw.jpg",
        "meta_description": "The generic meta description.",
        "title": "Widget Pro | Example Co",
        "h1": "Widget Pro Heading",
    }


def test_absent_tags_are_simply_absent():
    html = "<html><head></head><body>no tags here</body></html>"
    assert extract_page_metadata(html, BASE) == {}


def test_relative_image_urls_resolved_against_base():
    html = '<html><head><meta property="og:image" content="../images/x.jpg"></head></html>'
    meta = extract_page_metadata(html, "https://example.com/products/widget/")
    assert meta["og:image"] == "https://example.com/products/images/x.jpg"


def test_metadata_to_fields_prefers_og_title_over_h1_and_title():
    fields = metadata_to_fields({"og:title": "OG Name", "h1": "H1 Name", "title": "Title Tag"})
    assert fields["name"] == "OG Name"


def test_metadata_to_fields_falls_back_to_h1_then_title():
    assert metadata_to_fields({"h1": "H1 Name", "title": "Title Tag"})["name"] == "H1 Name"
    assert metadata_to_fields({"title": "Title Tag"})["name"] == "Title Tag"


def test_metadata_to_fields_prefers_og_description_over_meta_description():
    fields = metadata_to_fields({"og:description": "OG desc", "meta_description": "Meta desc"})
    assert fields["description"] == "OG desc"


def test_metadata_to_fields_prefers_og_image_over_twitter_image():
    fields = metadata_to_fields({"og:image": "https://x/a.jpg", "twitter:image": "https://x/b.jpg"})
    assert fields["image"] == "https://x/a.jpg"


def test_metadata_to_fields_empty_when_nothing_present():
    assert metadata_to_fields({}) == {}


def test_gallery_images_found_inside_product_container():
    html = """
    <html><body>
      <div class="product-gallery">
        <img src="/img/product-1.jpg" width="600" height="600">
        <img src="/img/logo.jpg" width="600" height="600">
      </div>
      <div class="nav-icons"><img src="/img/unrelated.jpg" width="600" height="600"></div>
    </body></html>
    """
    images = extract_gallery_images(html, BASE)
    assert images == ["https://example.com/img/product-1.jpg"]


def test_gallery_images_excludes_small_stated_dimensions():
    html = """
    <div class="gallery">
      <img src="/img/icon.jpg" width="20" height="20">
      <img src="/img/real-photo.jpg" width="800" height="600">
    </div>
    """
    assert extract_gallery_images(html, BASE) == ["https://example.com/img/real-photo.jpg"]


def test_gallery_images_no_stated_dimensions_not_excluded():
    html = '<div id="product-images"><img src="/img/photo.jpg"></div>'
    assert extract_gallery_images(html, BASE) == ["https://example.com/img/photo.jpg"]


def test_gallery_images_empty_when_no_container():
    html = '<div class="footer"><img src="/img/photo.jpg" width="800" height="600"></div>'
    assert extract_gallery_images(html, BASE) == []


def test_gallery_images_deduplicated():
    html = """
    <div class="product">
      <img src="/img/a.jpg"><img src="/img/a.jpg">
    </div>
    """
    assert extract_gallery_images(html, BASE) == ["https://example.com/img/a.jpg"]


def test_resolve_product_image_prefers_jsonld():
    html = '<html><head><meta property="og:image" content="/og.jpg"></head></html>'
    assert resolve_product_image({"image": "https://x/jsonld.jpg"}, html, BASE) == "https://x/jsonld.jpg"


def test_resolve_product_image_falls_back_to_metadata():
    html = '<html><head><meta property="og:image" content="/og.jpg"></head></html>'
    assert resolve_product_image({}, html, BASE) == "https://example.com/og.jpg"


def test_resolve_product_image_falls_back_to_gallery_scan():
    html = '<div class="product-gallery"><img src="/img/photo.jpg" width="500" height="500"></div>'
    assert resolve_product_image({}, html, BASE) == "https://example.com/img/photo.jpg"


def test_resolve_product_image_none_when_nothing_found():
    assert resolve_product_image({}, "<html></html>", BASE) is None


def test_resolve_product_image_none_when_no_html_and_no_jsonld_image():
    assert resolve_product_image({}, "", BASE) is None
