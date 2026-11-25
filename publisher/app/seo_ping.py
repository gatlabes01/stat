from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def ensure_indexnow_key_file(repo_root: Path, key: str | None) -> Path | None:
    """Write IndexNow verification file at repo root (served as /{key}.txt)."""
    if not key:
        return None
    key_path = repo_root / f"{key}.txt"
    if not key_path.exists() or key_path.read_text(encoding="utf-8").strip() != key:
        key_path.write_text(key + "\n", encoding="utf-8")
    return key_path


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


def submit_indexnow(site_host: str, key: str, url_list: list[str]) -> dict:
    """Notify Bing/Yandex/others via IndexNow (optional INDEXNOW_KEY on site root)."""
    if not key or not url_list:
        return {"skipped": "no_key_or_urls"}
    payload = {
        "host": site_host.replace("https://", "").replace("http://", "").strip("/"),
        "key": key,
        "urlList": url_list[:10000],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.indexnow.org/IndexNow",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return {"status": resp.status, "count": len(url_list)}
    except Exception as exc:
        log.warning("IndexNow submit failed: %s", exc)
        return {"error": str(exc)}