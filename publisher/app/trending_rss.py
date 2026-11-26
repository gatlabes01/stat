from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
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


def _news_items(item: ET.Element) -> list[TrendNewsItem]:
    out: list[TrendNewsItem] = []
    for block in item.findall(f"{{{HT_NS}}}news_item"):
        out.append(
            TrendNewsItem(
                title=_text(block.find(f"{{{HT_NS}}}news_item_title")),
                url=_text(block.find(f"{{{HT_NS}}}news_item_url")),
                source=_text(block.find(f"{{{HT_NS}}}news_item_source")),
                picture=_text(block.find(f"{{{HT_NS}}}news_item_picture")),
            )
        )
    return [n for n in out if n.title]


def parse_trends_rss(xml_text: str) -> list[TrendItem]:
    text = (xml_text or "").lstrip()
    if not text.startswith("<"):
        logger.warning("Trends response is not XML (%s chars)", len(text))
        return []
    root = ET.fromstring(text)
    channel = root.find("channel")
    if channel is None:
        return []
    items: list[TrendItem] = []
    for item in channel.findall("item"):
        keyword = _text(item.find("title"))
        if not keyword:
            continue
        approx = _text(item.find(f"{{{HT_NS}}}approx_traffic"))
        score = parse_traffic_score(approx)
        items.append(
            TrendItem(
                keyword=keyword,
                approx_traffic=approx,
                traffic_score=score,
                pub_date=_text(item.find("pubDate")),
                picture=_text(item.find(f"{{{HT_NS}}}picture")),
                picture_source=_text(item.find(f"{{{HT_NS}}}picture_source")),
                news=_news_items(item),
            )
        )
    items.sort(key=lambda x: x.traffic_score, reverse=True)
    return items


def _rss_url(geo: str) -> str:
    url = SETTINGS.trending_rss_url
    if "{geo}" in url:
        return url.format(geo=geo)
    if "geo=" not in url and geo:
        return f"https://trends.google.com/trending/rss?geo={geo}"
    return url


def fetch_us_trending(geo: str | None = None) -> list[TrendItem]:
    geo = geo or SETTINGS.trending_geo
    url = _rss_url(geo)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=45.0, follow_redirects=True) as client:
                response = client.get(url, headers=_HEADERS)
                response.raise_for_status()
            items = parse_trends_rss(response.text)
            if items:
                logger.info("Google Trends RSS: %s items (geo=%s)", len(items), geo)
                return items
            logger.warning(
                "Google Trends RSS parsed 0 items (status=%s, %s chars, attempt %s)",
                response.status_code,
                len(response.text or ""),
                attempt + 1,
            )
        except Exception as exc:
            last_error = exc
            logger.warning("Google Trends RSS fetch failed (attempt %s): %s", attempt + 1, exc)
    if last_error:
        raise last_error
    raise RuntimeError(f"Google Trends RSS returned 0 items from {url}")