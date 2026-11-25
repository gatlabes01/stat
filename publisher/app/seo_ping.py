from __future__ import annotations

import logging
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)


def ping_sitemap(sitemap_url: str) -> dict:
    """Tell Google/Bing to recrawl the news sitemap after a publish."""
    results: dict[str, str] = {}
    for name, base in (
        ("google", "https://www.google.com/ping?sitemap="),
        ("bing", "https://www.bing.com/ping?sitemap="),
    ):
        url = base + urllib.parse.quote(sitemap_url, safe="")
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                results[name] = f"ok:{resp.status}"
        except Exception as exc:
            log.warning("%s sitemap ping failed: %s", name, exc)
            results[name] = f"error:{exc}"
    return results