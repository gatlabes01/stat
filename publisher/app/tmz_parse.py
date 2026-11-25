from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape

import httpx

_USER_AGENT = "Mozilla/5.0 (compatible; DetailzBot/1.0)"


@dataclass
class ArticleImage:
    url: str
    credit: str | None = None


@dataclass
class ParsedArticle:
    headline: str
    paragraphs: list[str]
    images: list[ArticleImage]
    image_after_paragraph: list[tuple[int, int]]  # (paragraph_index, image_index)


def _upgrade_image(url: str) -> str:
    return re.sub(r"_(xs|sm|md|lg)(\.[a-z]+)$", r"_xl\2", url, flags=re.I)


def _image_key(url: str) -> str:
    m = re.search(r"/([a-f0-9]{32})_", url, re.I)
    return m.group(1) if m else url


def _parse_ld_json(html: str) -> dict | None:
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    ):
        data = json.loads(match.group(1).strip())
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _credit_map(ld: dict) -> dict[str, str]:
    credits: dict[str, str] = {}
    images = ld.get("image") or []
    if isinstance(images, str):
        images = [images]
    for item in images:
        if isinstance(item, str):
            credits[_image_key(item)] = ""
        elif isinstance(item, dict):
            url = item.get("url") or ""
            credits[_image_key(url)] = (item.get("creditText") or "").strip()
    return credits


def _article_chunk(html: str) -> str:
    h1 = re.search(r"<h1[^>]*>", html, re.I)
    if not h1:
        return html[:80000]
    start = h1.start()
    rel = re.search(
        r'(?:class="[^"]*(?:related|more-stories|you-might)[^"]*"|id="related")',
        html[start:],
        re.I,
    )
    end = start + rel.start() if rel else start + 60000
    return html[start:end]


def _clean_paragraph(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_tmz_article(url: str, timeout: float = 20.0) -> ParsedArticle | None:
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError:
        return None

    ld = _parse_ld_json(html)
    if not ld:
        return None

    headline = (ld.get("headline") or "").strip()
    body = (ld.get("articleBody") or "").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
    if not paragraphs:
        return None

    credits = _credit_map(ld)
    chunk = _article_chunk(html)

    ordered_images: list[str] = []
    for match in re.finditer(r"https://imagez\.tmz\.com/image/[^\"'\s<>]+", chunk):
        raw = match.group(0).split("?")[0]
        if not re.search(r"\.(?:jpg|jpeg|png|webp)$", raw, re.I):
            continue
        key = _image_key(raw)
        if any(_image_key(u) == key for u in ordered_images):
            continue
        ordered_images.append(_upgrade_image(raw))

    images = [
        ArticleImage(url=u, credit=credits.get(_image_key(u)) or None)
        for u in ordered_images
    ]

    events: list[tuple[int, str, str]] = []
    para_idx = -1
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", chunk, re.S | re.I):
        text = _clean_paragraph(match.group(1))
        if len(text) < 35 or "wbq.push" in text or "preloadImage" in text:
            continue
        para_idx += 1
        events.append((match.start(), "p", str(para_idx)))

    img_positions: list[tuple[int, int]] = []
    img_i = 0
    current_para = 0
    for match in re.finditer(r"https://imagez\.tmz\.com/image/[^\"'\s<>]+", chunk):
        pos = match.start()
        raw = match.group(0).split("?")[0]
        key = _image_key(raw)
        while events and events[0][0] < pos:
            if events[0][1] == "p":
                current_para = int(events[0][2])
            events.pop(0)
        if img_i < len(images) and _image_key(images[img_i].url) == key:
            img_positions.append((max(0, current_para), img_i))
            img_i += 1

    if not img_positions and images:
        img_positions = [(min(i, len(paragraphs) - 1), i) for i in range(len(images))]

    return ParsedArticle(
        headline=headline,
        paragraphs=paragraphs,
        images=images,
        image_after_paragraph=img_positions,
    )