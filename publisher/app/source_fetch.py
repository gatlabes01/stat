from __future__ import annotations

import re
from html import unescape

import httpx

_USER_AGENT = (
    "DetailzBot/1.0 (+https://localhost; entertainment news aggregator)"
)


def _meta(html: str, key: str, *, prop: bool = True) -> str | None:
    attr = "property" if prop else "name"
    pattern = rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)'
    match = re.search(pattern, html, re.I)
    if not match:
        pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+{attr}=["\']{re.escape(key)}["\']'
        match = re.search(pattern, html, re.I)
    return unescape(match.group(1)).strip() if match else None


def fetch_page_context(url: str, timeout: float = 15.0) -> dict:
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text[:500_000]
    except httpx.HTTPError:
        return {}

    description = (
        _meta(html, "og:description")
        or _meta(html, "description", prop=False)
        or _meta(html, "twitter:description", prop=False)
    )
    image = _meta(html, "og:image")
    headline = _meta(html, "og:title")
    return {
        "page_description": description,
        "page_headline": headline,
        "image_url": image,
    }