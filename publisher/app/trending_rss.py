from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import SETTINGS

logger = logging.getLogger(__name__)

HT_NS = "https://trends.google.com/trending/rss"


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
    root = ET.fromstring(xml_text)
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


def fetch_us_trending(geo: str | None = None) -> list[TrendItem]:
    geo = geo or SETTINGS.trending_geo
    url = SETTINGS.trending_rss_url
    if "{geo}" in url:
        url = url.format(geo=geo)
    elif "geo=" not in url and geo:
        url = f"https://trends.google.com/trending/rss?geo={geo}"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers={"User-Agent": "DetailzTrendingBot/1.0"})
        response.raise_for_status()
    return parse_trends_rss(response.text)