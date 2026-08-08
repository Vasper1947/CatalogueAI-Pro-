"""find_media / capture_full_page_snapshot: video and .gif discovery from
page markup, and a full-page screenshot via Playwright's own capability.
"""

from scraper.discover import capture_full_page_snapshot, find_media

BASE = "https://example.com/products/hinge-demo"


def test_video_source_is_found_and_url_resolved():
    html = """
    <html><body>
      <video><source src="/media/demo.mp4" type="video/mp4"></video>
    </body></html>
    """
    result = find_media(html, BASE)
    assert result == [{"url": "https://example.com/media/demo.mp4", "media_type": "video"}]


def test_video_src_attribute_directly_on_video_tag():
    html = '<video src="clip.webm"></video>'
    result = find_media(html, BASE)
    assert result == [{"url": "https://example.com/products/clip.webm", "media_type": "video"}]


def test_gif_image_reference_is_found():
    html = '<img src="/img/animation.gif" alt="demo">'
    result = find_media(html, BASE)
    assert result == [{"url": "https://example.com/img/animation.gif", "media_type": "gif"}]


def test_gif_with_query_string_still_matches():
    html = '<img src="/img/demo.gif?v=2" alt="demo">'
    result = find_media(html, BASE)
    assert result == [{"url": "https://example.com/img/demo.gif?v=2", "media_type": "gif"}]


def test_non_gif_image_is_not_matched():
    html = '<img src="/img/photo.jpg" alt="photo">'
    assert find_media(html, BASE) == []


def test_duplicate_media_urls_deduplicated():
    html = """
    <video src="demo.mp4"></video>
    <a href="demo.mp4">download</a>
    """
    result = find_media(html, BASE)
    assert len(result) == 1


def test_no_media_at_all_returns_empty_list():
    assert find_media("<div>plain content, no media</div>", BASE) == []


def test_mixed_video_and_gif_both_captured():
    html = """
    <video><source src="clip.mp4"></video>
    <img src="loop.gif">
    """
    result = find_media(html, BASE)
    types = {r["media_type"] for r in result}
    assert types == {"video", "gif"}


class _FakePage:
    """A minimal stand-in for a Playwright Page -- proves
    capture_full_page_snapshot calls the real screenshot API correctly,
    without needing a live browser for this unit test."""

    def __init__(self, return_bytes: bytes):
        self._return_bytes = return_bytes
        self.calls: list[dict] = []

    def screenshot(self, **kwargs):
        self.calls.append(kwargs)
        return self._return_bytes


def test_capture_full_page_snapshot_calls_playwrights_own_screenshot_api():
    fake = _FakePage(b"\x89PNG-fake-snapshot-bytes")
    result = capture_full_page_snapshot(fake)

    assert result == b"\x89PNG-fake-snapshot-bytes"
    assert fake.calls == [{"full_page": True}]
