from __future__ import annotations

import re
import unicodedata


def slugify(text: str, max_length: int = 80) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]
    return text or "story"


def unique_slug(conn, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    n = 2
    while conn.execute("SELECT 1 FROM stories WHERE slug = ?", (candidate,)).fetchone():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate