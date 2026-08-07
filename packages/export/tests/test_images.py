"""process_image: pure WebP conversion + naming. No background removal, no
compositing this slice -- format conversion only.
"""

import io

from export.images import WEBP_QUALITY, process_image
from PIL import Image


def _real_png_bytes(size=(20, 16), color="blue") -> bytes:
    """A genuinely valid, real PNG image (generated, not scraped) -- proves
    process_image works on real image data, not just arbitrary bytes."""
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_process_image_produces_a_valid_correctly_named_webp(tmp_path):
    raw = _real_png_bytes(size=(20, 16))

    out_path = process_image("P1", 0, raw, output_dir=tmp_path)

    assert out_path == tmp_path / "P1_0.webp"
    assert out_path.exists()
    with Image.open(out_path) as img:
        img.load()
        assert img.format == "WEBP"
        assert img.size == (20, 16)


def test_process_image_naming_uses_record_id_and_index(tmp_path):
    raw = _real_png_bytes()
    p0 = process_image("sku-123", 0, raw, output_dir=tmp_path)
    p1 = process_image("sku-123", 1, raw, output_dir=tmp_path)

    assert p0.name == "sku-123_0.webp"
    assert p1.name == "sku-123_1.webp"


def test_webp_quality_is_a_named_tunable_constant():
    # Named + tunable, same discipline as MATCH_THRESHOLD/RECALL_THRESHOLD.
    assert isinstance(WEBP_QUALITY, int)
    assert WEBP_QUALITY == 88
