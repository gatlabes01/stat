"""Fetch TMZ RSS, auto-enrich, and publish to Detailz."""

from __future__ import annotations

import re
from email.utils import parsedate_to_datetime

import feedparser

from app.config import SETTINGS
from app.database import connect, init_db, upsert_story
from app.enrich import enrich_pending

TMZ_RSS_URL = SETTINGS.tmz_rss_url
COPYRIGHT_NOTICE = (
    "Stories on Detailz are independent rewrites based on publicly reported entertainment news. "
    "Source links are provided for attribution."
)


def _first_image(entry: feedparser.FeedParserDict) -> str | None:
    if getattr(entry, "media_thumbnail", None):
        return entry.media_thumbnail[0].get("url")
    if getattr(entry, "media_content", None):
        for item in entry.media_content:
            if item.get("medium") == "image" or "image" in (item.get("type") or ""):
                return item.get("url")
    if getattr(entry, "links", None):
        for link in entry.links:
            if link.get("type", "").startswith("image/"):
                return link.get("href")
    return None


def _published_iso(entry: feedparser.FeedParserDict) -> str | None:
    if getattr(entry, "published", None):
        try:
            return parsedate_to_datetime(entry.published).isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
    if getattr(entry, "updated", None):
        return str(entry.updated)
    return None


def _summary(entry: feedparser.FeedParserDict) -> str | None:
    raw = entry.get("summary") or entry.get("description")
    if not raw:
        return None
    text = re.sub(r"<[^>]+>", "", raw).strip()
    return text or None


def fetch_tmz_stories() -> list[dict]:
    parsed = feedparser.parse(TMZ_RSS_URL)
    if parsed.bozo and not parsed.entries:
        err = getattr(parsed, "bozo_exception", None)
        raise RuntimeError(f"Failed to parse TMZ feed: {err}")

    stories: list[dict] = []
    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("guid") or entry.get("link")
        link = entry.get("link")
        title = (entry.get("title") or "").strip()
        if not guid or not link or not title:
            continue
        stories.append(
            {
                "guid": guid,
                "title": title,
                "link": link,
                "summary": _summary(entry),
                "author": entry.get("author"),
                "published_at": _published_iso(entry),
                "image_url": _first_image(entry),
            }
        )
    return stories


def sync_tmz() -> dict:
    conn = connect()
    init_db(conn)
    stories = fetch_tmz_stories()
    new_ids: list[int] = []
    for story in stories:
        story_id, is_new = upsert_story(conn, story)
        if is_new:
            new_ids.append(story_id)
    total = conn.execute("SELECT COUNT(*) AS n FROM stories").fetchone()["n"]
    conn.close()

    enrich_stats = enrich_pending(
        limit=max(SETTINGS.enrich_batch_size, len(new_ids) + 2)
    )

    conn = connect()
    published = conn.execute(
        "SELECT COUNT(*) AS n FROM stories WHERE status = 'published'"
    ).fetchone()["n"]
    new_slugs: list[str] = []
    if new_ids:
        placeholders = ",".join("?" * len(new_ids))
        rows = conn.execute(
            f"""
            SELECT slug FROM stories
            WHERE id IN ({placeholders}) AND status = 'published' AND slug IS NOT NULL
            """,
            new_ids,
        ).fetchall()
        new_slugs = [str(r["slug"]) for r in rows if r["slug"]]
    conn.close()

    return {
        "fetched": len(stories),
        "new_stories": len(new_ids),
        "new_slugs": new_slugs,
        "total_in_db": total,
        "published": published,
        "enriched_this_run": enrich_stats["enriched"],
        "enrich_failed": enrich_stats["failed"],
        "source": TMZ_RSS_URL,
        "notice": COPYRIGHT_NOTICE,
    }


def main() -> None:
    result = sync_tmz()
    print(
        f"Fetched {result['fetched']}; {result['new_stories']} new; "
        f"{result['enriched_this_run']} published with SEO rewrites."
    )


if __name__ == "__main__":
    main()