"""Image processing: pure format conversion to WebP. No background removal,
no compositing this slice -- that is explicitly out of scope here.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

# WebP quality, named + tunable (same discipline as engine.detect's
# MATCH_THRESHOLD/RECALL_THRESHOLD). 100 is near-lossless and produces
# meaningfully larger files for marginal visual gain over ~85-90 on
# photographic content, so 88 is a deliberate high-quality-but-compressed
# default appropriate for product catalog images, not an arbitrary number.
WEBP_QUALITY = 88


def process_image(record_id: str, index: int, raw_bytes: bytes, *, output_dir) -> Path:
    """Convert raw image bytes to WebP and write <record_id>_<index>.webp
    into output_dir. Returns the written path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{record_id}_{index}.webp"

    with Image.open(io.BytesIO(raw_bytes)) as img:
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img.save(out_path, format="WEBP", quality=WEBP_QUALITY)

    return out_path
