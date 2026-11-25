"""Keep trending pages on-topic: headlines must mention the search keyword."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from app.trending_rss import TrendItem, TrendNewsItem

_STOP = {
    "a", "an", "the", "and", "or", "for", "of", "in", "on", "at", "to", "vs", "v",
    "with", "from", "by", "de", "del", "la", "el",
}
_GENERIC = {
    "state", "news", "game", "games", "today", "week", "live", "update", "updates",
    "score", "scores", "record", "numbers", "number", "season", "team", "teams",
}


def keyword_tokens(keyword: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (keyword or "").lower())
    return [w for w in words if len(w) >= 3 and w not in _STOP]


def distinctive_tokens(keyword: str) -> list[str]:
    tokens = keyword_tokens(keyword)
    distinctive = [t for t in tokens if t not in _GENERIC]
    return distinctive or tokens


def headline_score(title: str, keys: list[str]) -> int:
    blob = (title or "").lower()
    return sum(1 for k in keys if k in blob)


def relevant_news(item: TrendItem) -> list[TrendNewsItem]:
    keys = distinctive_tokens(item.keyword)
    if not keys:
        return list(item.news)
    ranked = sorted(
        ((headline_score(n.title, keys), n) for n in item.news if n.title),
        key=lambda pair: -pair[0],
    )
    return [n for score, n in ranked if score > 0]


def align_trend_item(item: TrendItem) -> TrendItem:
    """Reorder and drop headlines that do not mention the keyword."""
    return replace(item, news=relevant_news(item))


def is_on_topic(item: TrendItem) -> bool:
    aligned = align_trend_item(item)
    return bool(aligned.news) or not item.news


def filter_source_links_json(keyword: str, source_links: str | None) -> str:
    try:
        raw = json.loads(source_links or "[]")
    except json.JSONDecodeError:
        return source_links or "[]"
    news = [
        TrendNewsItem(
            title=str(x.get("title") or ""),
            url=str(x.get("url") or ""),
            source=str(x.get("source") or ""),
            picture="",
        )
        for x in raw
        if isinstance(x, dict)
    ]
    item = TrendItem(
        keyword=keyword,
        approx_traffic="",
        traffic_score=0,
        pub_date="",
        picture="",
        picture_source="",
        news=news,
    )
    kept = relevant_news(item)
    if not kept and news:
        kept = []
    payload = [
        {"title": n.title, "url": n.url, "source": n.source}
        for n in kept
    ]
    return json.dumps(payload, ensure_ascii=False)
