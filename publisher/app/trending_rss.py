from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import SETTINGS

logger = logging.getLogger(__name__)

HT_NS = "https://trends.google.com/trending/rss"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class TrendNewsItem:
    title: str
    url: str
    source: str
    picture: str


@dataclass
class TrendItem:
    keyword: str
    approx_traffic: str
    traffic_score: int
    pub_date: str
    picture: str
    picture_source: str
    news: list[TrendNewsItem] = field(default_factory=list)


def parse_traffic_score(raw: str | None) -> int:
    if not raw:
        return 0
    s = raw.strip().replace(",", "").rstrip("+").upper()
    mult = 1
    for suffix, m in (("M", 1_000_000), ("K", 1_000)):
        if s.endswith(suffix):
            mult = m
            s = s[: -len(suffix)]
            break
    try:
        return int(float(s) * mult)
    except ValueError:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _local(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for child in el:
        if _local(child.tag) == name:
            return child
    return None


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _news_items(item: ET.Element) -> list[TrendNewsItem]:
    out: list[TrendNewsItem] = []
    for block in _children(item, "news_item"):
        out.append(
            TrendNewsItem(
                title=_text(_child(block, "news_item_title")),
                url=_text(_child(block, "news_item_url")),
                source=_text(_child(block, "news_item_source")),
                picture=_text(_child(block, "news_item_picture")),
            )
        )
    return [n for n in out if n.title]


def parse_trends_rss(xml_text: str) -> list[TrendItem]:
    text = (xml_text or "").lstrip("\ufeff \t\r\n")
    if "<item" not in text.lower():
        logger.warning("Trends response has no <item> (%s chars)", len(text))
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("Trends XML parse error: %s", exc)
        return []
    channel = root.find("channel")
    if channel is None:
        channel = _child(root, "channel")
    if channel is None:
        return []
    items: list[TrendItem] = []
    for item in _children(channel, "item"):
        keyword = _text(_child(item, "title"))
        if not keyword:
            continue
        approx = _text(_child(item, "approx_traffic"))
        score = parse_traffic_score(approx)
        items.append(
            TrendItem(
                keyword=keyword,
                approx_traffic=approx,
                traffic_score=score,
                pub_date=_text(_child(item, "pubDate")),
                picture=_text(_child(item, "picture")),
                picture_source=_text(_child(item, "picture_source")),
                news=_news_items(item),
            )
        )
    items.sort(key=lambda x: x.traffic_score, reverse=True)
    return items


def _rss_urls(geo: str) -> list[str]:
    urls: list[str] = []
    primary = SETTINGS.trending_rss_url
    if "{geo}" in primary:
        primary = primary.format(geo=geo)
    urls.append(primary)
    urls.append(f"https://trends.google.com/trending/rss?geo={geo}")
    urls.append(f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}")
    out: list[str] = []
    for url in urls:
        if url not in out:
            out.append(url)
    return out


def _items_from_file(path: Path) -> list[TrendItem]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    items = parse_trends_rss(text)
    logger.info("Trends RSS file %s: %s items", path, len(items))
    return items


def fetch_us_trending(geo: str | None = None) -> list[TrendItem]:
    geo = geo or SETTINGS.trending_geo
    file_raw = (os.environ.get("TRENDS_RSS_FILE") or "").strip()
    if file_raw:
        path = Path(file_raw)
        if path.is_file():
            items = _items_from_file(path)
            if items:
                return items
            logger.warning("TRENDS_RSS_FILE had 0 items, trying HTTP")

    last_error: Exception | None = None
    for url in _rss_urls(geo):
        for attempt in range(3):
            try:
                with httpx.Client(timeout=45.0, follow_redirects=True) as client:
                    response = client.get(url, headers=_HEADERS)
                logger.info(
                    "Trends GET %s -> %s (%s chars)",
                    url,
                    response.status_code,
                    len(response.text or ""),
                )
                response.raise_for_status()
                items = parse_trends_rss(response.text)
                if items:
                    logger.info("Google Trends RSS: %s items from %s", len(items), url)
                    return items
                logger.warning("Parsed 0 items from %s (attempt %s)", url, attempt + 1)
            except Exception as exc:
                last_error = exc
                logger.warning("Trends fetch failed %s attempt %s: %s", url, attempt + 1, exc)
                time.sleep(2)
    if last_error:
        raise last_error
    raise RuntimeError("Google Trends RSS returned 0 items from all URLs")
