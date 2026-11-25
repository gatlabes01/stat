from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import httpx

from app.config import SETTINGS
from app.trending_db import (
    connect,
    get_by_normalized,
    init_db,
    insert_topic,
    normalize_keyword,
    unique_trending_slug,
    utc_now,
)
from app.trending_enrich import build_article
from app.trending_rss import fetch_us_trending

logger = logging.getLogger(__name__)


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


def sync_trending() -> dict:
    items = fetch_us_trending()
    conn = connect()
    init_db(conn)

    min_score = SETTINGS.trending_min_traffic_score
    max_new = SETTINGS.trending_max_per_run
    created = 0
    skipped_existing = 0
    skipped_low = 0
    new_slugs: list[str] = []

    for item in items:
        if created >= max_new:
            break
        if item.traffic_score < min_score:
            skipped_low += 1
            continue
        norm = normalize_keyword(item.keyword)
        if get_by_normalized(conn, norm):
            skipped_existing += 1
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
        logger.info("Trending article created: %s (%s)", item.keyword, slug)

    conn.close()
    return {
        "fetched": len(items),
        "new_articles": created,
        "skipped_existing": skipped_existing,
        "skipped_low_traffic": skipped_low,
        "new_slugs": new_slugs,
    }