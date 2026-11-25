from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

import httpx

from app.config import SETTINGS
from app.trending_db import (
    connect,
    count_by_normalized,
    init_db,
    insert_topic,
    latest_by_normalized,
    normalize_keyword,
    unique_trending_slug,
    utc_now,
)
from app.trending_enrich import build_article
from app.trending_rss import TrendItem, fetch_us_trending

logger = logging.getLogger(__name__)


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def news_fingerprint_from_item(item: TrendItem) -> str:
    titles = sorted(
        _norm_title(n.title) for n in (item.news or [])[:8] if _norm_title(n.title)
    )
    return "|".join(titles)


def news_fingerprint_from_stored(source_links: str | None) -> str:
    try:
        items = json.loads(source_links or "[]")
        titles = sorted(
            _norm_title(x.get("title", "")) for x in items if _norm_title(x.get("title", ""))
        )
        return "|".join(titles)
    except (json.JSONDecodeError, TypeError):
        return ""


def news_sources_changed(latest_row, item: TrendItem) -> bool:
    if latest_row is None:
        return True
    prev = news_fingerprint_from_stored(latest_row["source_links"])
    curr = news_fingerprint_from_item(item)
    if not curr:
        return False
    return prev != curr


def _media_root() -> Path:
    from app.paths import project_root

    return project_root() / "data" / "trending_media"


def _cache_image(slug: str, url: str) -> str | None:
    if not url or not url.startswith("http"):
        return None
    dest_dir = _media_root() / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "01.jpg"
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "DetailzTrendingBot/1.0"})
            response.raise_for_status()
        dest.write_bytes(response.content)
        return f"/trending/media/{slug}/01.jpg"
    except Exception as exc:
        logger.warning("Image cache failed for %s: %s", slug, exc)
        return url


def _sort_for_publishing(conn: sqlite3.Connection, items: list[TrendItem]) -> list[TrendItem]:
    """Prefer keywords eligible for a new edition (under cap, news changed)."""

    def key(item: TrendItem) -> tuple:
        norm = normalize_keyword(item.keyword)
        n = count_by_normalized(conn, norm)
        latest = latest_by_normalized(conn, norm)
        changed = 1 if news_sources_changed(latest, item) else 0
        return (-changed, n, -item.traffic_score)

    eligible = [i for i in items if i.traffic_score >= SETTINGS.trending_min_traffic_score]
    return sorted(eligible, key=key)


def sync_trending() -> dict:
    items = fetch_us_trending()
    conn = connect()
    init_db(conn)

    max_new = SETTINGS.trending_max_per_run
    max_per_kw = SETTINGS.trending_max_per_keyword
    created = 0
    skipped_at_cap = 0
    skipped_unchanged = 0
    new_slugs: list[str] = []

    skipped_low = len(items) - len(
        [i for i in items if i.traffic_score >= SETTINGS.trending_min_traffic_score]
    )

    for item in _sort_for_publishing(conn, items):
        if created >= max_new:
            break
        norm = normalize_keyword(item.keyword)
        existing = count_by_normalized(conn, norm)
        if existing >= max_per_kw:
            skipped_at_cap += 1
            continue

        latest = latest_by_normalized(conn, norm)
        if existing > 0 and not news_sources_changed(latest, item):
            skipped_unchanged += 1
            continue

        slug = unique_trending_slug(conn, item.keyword)
        local_img = _cache_image(slug, item.picture)
        article = build_article(item, local_img or item.picture)
        now = utc_now()

        insert_topic(
            conn,
            {
                "keyword": item.keyword,
                "keyword_normalized": norm,
                "slug": slug,
                "approx_traffic": item.approx_traffic,
                "traffic_score": item.traffic_score,
                "seo_title": article["seo_title"],
                "h1": article["h1"],
                "meta_description": article["meta_description"],
                "article_body": article["article_body"],
                "image_url": local_img or item.picture or "",
                "source_links": article["source_links"],
                "faq_json": article["faq_json"],
                "seo_keywords": article["seo_keywords"],
                "status": "published",
                "published_at": now,
                "created_at": now,
                "trend_pub_date": item.pub_date,
            },
        )
        created += 1
        new_slugs.append(slug)
        edition = existing + 1
        logger.info(
            "Trending article created: %s (%s) edition %s/%s (news updated)",
            item.keyword,
            slug,
            edition,
            max_per_kw,
        )

    conn.close()
    return {
        "fetched": len(items),
        "new_articles": created,
        "skipped_at_keyword_cap": skipped_at_cap,
        "skipped_unchanged_news": skipped_unchanged,
        "skipped_low_traffic": skipped_low,
        "new_slugs": new_slugs,
        "max_per_keyword": max_per_kw,
    }