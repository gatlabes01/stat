from __future__ import annotations

from datetime import datetime


def format_story_date(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00")) if "T" in text else datetime.strptime(text, fmt)
            return dt.strftime("%B %d, %Y")
        except ValueError:
            continue
    return text[:10] if len(text) >= 10 else text