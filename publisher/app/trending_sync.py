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

    init_db,

    insert_topic,

    latest_by_normalized,

    normalize_keyword,

    unique_trending_slug,

    update_topic,

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

    webp = dest_dir / "01.webp"
    jpeg = dest_dir / "01.jpg"

    if webp.is_file() and webp.stat().st_size > 0:
        return f"/trending/media/{slug}/01.webp"
    if jpeg.is_file() and jpeg.stat().st_size > 0:
        return f"/trending/media/{slug}/01.jpg"

    try:

        with httpx.Client(timeout=45.0, follow_redirects=True) as client:

            response = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    )
                },
            )

            response.raise_for_status()

        from app.webp_image import save_as_webp

        if save_as_webp(response.content, webp):
            return f"/trending/media/{slug}/01.webp"

        jpeg.write_bytes(response.content)

        return f"/trending/media/{slug}/01.jpg"

    except Exception as exc:

        logger.warning("Image cache failed for %s: %s", slug, exc)

        if webp.is_file() and webp.stat().st_size > 0:
            return f"/trending/media/{slug}/01.webp"
        if jpeg.is_file() and jpeg.stat().st_size > 0:
            return f"/trending/media/{slug}/01.jpg"
        return url





def _row_from_item(item: TrendItem, slug: str, image_url: str) -> dict:

    article = build_article(item, image_url)

    now = utc_now()

    return {

        "keyword": item.keyword,

        "keyword_normalized": normalize_keyword(item.keyword),

        "slug": slug,

        "approx_traffic": item.approx_traffic,

        "traffic_score": item.traffic_score,

        "seo_title": article["seo_title"],

        "h1": article["h1"],

        "meta_description": article["meta_description"],

        "article_body": article["article_body"],

        "image_url": image_url,

        "source_links": article["source_links"],

        "faq_json": article["faq_json"],

        "seo_keywords": article["seo_keywords"],

        "status": "published",

        "published_at": now,

        "created_at": now,

        "trend_pub_date": item.pub_date,

    }





def _update_row_from_item(row, item: TrendItem) -> dict:

    slug = row["slug"]

    image_url = _cache_image(slug, item.picture) or row["image_url"] or item.picture or ""

    article = build_article(item, image_url or None)

    now = utc_now()

    return {

        "approx_traffic": item.approx_traffic,

        "traffic_score": item.traffic_score,

        "seo_title": article["seo_title"],

        "h1": article["h1"],

        "meta_description": article["meta_description"],

        "article_body": article["article_body"],

        "image_url": image_url,

        "source_links": article["source_links"],

        "faq_json": article["faq_json"],

        "seo_keywords": article["seo_keywords"],

        "published_at": now,

        "trend_pub_date": item.pub_date,

    }





def sync_trending() -> dict:

    """New keywords get a page; existing topics refresh in place when headlines change."""

    items = fetch_us_trending()

    conn = connect()

    init_db(conn)



    max_new = SETTINGS.trending_max_per_run

    created = 0

    updated = 0

    skipped_unchanged = 0

    new_slugs: list[str] = []

    updated_slugs: list[str] = []

    skipped_low = sum(
        1 for i in items if i.traffic_score < SETTINGS.trending_min_traffic_score
    )

    by_traffic = sorted(
        [i for i in items if i.traffic_score >= SETTINGS.trending_min_traffic_score],
        key=lambda i: -i.traffic_score,
    )



    norm_refresh: dict[str, TrendItem] = {}

    for item in by_traffic:

        norm = normalize_keyword(item.keyword)

        norm_refresh.setdefault(norm, item)



    for norm, item in norm_refresh.items():

        latest = latest_by_normalized(conn, norm)

        if not latest:

            continue

        if not news_sources_changed(latest, item):

            skipped_unchanged += 1

            continue

        fields = _update_row_from_item(latest, item)

        update_topic(conn, int(latest["id"]), fields)

        updated += 1

        updated_slugs.append(latest["slug"])

        logger.info("Trending refreshed: %s (%s) — headlines updated", item.keyword, latest["slug"])



    for item in by_traffic:

        if created >= max_new:

            break

        norm = normalize_keyword(item.keyword)

        if latest_by_normalized(conn, norm):

            continue



        slug = unique_trending_slug(conn, item.keyword)

        image_url = _cache_image(slug, item.picture) or item.picture or ""

        row = _row_from_item(item, slug, image_url)

        insert_topic(conn, row)

        created += 1

        new_slugs.append(slug)

        logger.info("Trending article created: %s (%s)", item.keyword, slug)



    conn.close()

    return {

        "fetched": len(items),

        "new_articles": created,

        "updated_articles": updated,

        "skipped_unchanged_news": skipped_unchanged,

        "skipped_low_traffic": skipped_low,

        "new_slugs": new_slugs,

        "updated_slugs": updated_slugs,

    }
