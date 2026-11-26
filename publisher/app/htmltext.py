from __future__ import annotations

import re
from html import unescape


def decode_html_text(text: str | None) -> str:
    """Turn RSS/HTML entities into real characters (fix &amp;hellip; / orhellip)."""
    if not text:
        return ""
    t = unescape(unescape(str(text)))
    t = t.replace("\xa0", " ")
    t = re.sub(r"&(?:amp;)?hellip;?", "…", t, flags=re.I)
    t = re.sub(r"&#0*8230;?", "…", t)
    t = re.sub(r"&#x0*2026;?", "…", t, flags=re.I)
    t = re.sub(r"(?i)([A-Za-z0-9])hellip;?", r"\1…", t)
    return t
