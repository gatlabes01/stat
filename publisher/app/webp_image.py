from __future__ import annotations

from io import BytesIO
from pathlib import Path


def save_as_webp(data: bytes, dest: Path, max_width: int = 780, quality: int = 80) -> bool:
    """Resize and write a photo as WebP. Returns False if conversion fails."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        im = Image.open(BytesIO(data))
        if im.mode not in ("RGB",):
            im = im.convert("RGB")
        if im.width > max_width and im.width > 0:
            height = max(1, int(im.height * max_width / im.width))
            im = im.resize((max_width, height), Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "WEBP", quality=quality, method=4)
        return dest.is_file() and dest.stat().st_size > 0
    except Exception:
        return False
