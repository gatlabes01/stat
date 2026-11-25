from __future__ import annotations

from datetime import datetime, timezone


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
            dt = (
                datetime.fromisoformat(text.replace("Z", "+00:00"))
                if "T" in text
                else datetime.strptime(text, fmt)
            )
            return dt.strftime("%B %d, %Y")
        except ValueError:
            continue
    return text[:10] if len(text) >= 10 else text


def to_iso8601(raw: str | None) -> str:
    """Schema-friendly ISO-8601 (UTC when possible)."""
    if not raw:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    text = raw.strip()
    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except ValueError:
        pass
    if len(text) >= 10:
        return f"{text[:10]}T12:00:00+00:00"
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")