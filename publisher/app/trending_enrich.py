from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

import httpx

from app.config import SETTINGS
from app.trending_rss import TrendItem

logger = logging.getLogger(__name__)

TRENDING_SYSTEM = """You write short trending-search explainers for Detailz readers.
Rules:
- The primary keyword MUST appear in seo_title and meta_description naturally.
- seo_title: 50-65 chars, include the exact trending keyword phrase, engaging for Google.
- meta_description: 140-160 chars, include the keyword, summarize why people search it.
- paragraphs: 4-6 factual paragraphs using ONLY facts from the provided news headlines/links context.
- Do not invent statistics, quotes, or events not implied by the sources.
- End with a neutral "what to watch next" line — no hype.
Return JSON: seo_title, h1 (must contain exact keyword), meta_description, paragraphs (array),
keywords (5-8 phrases), faq (array of {q, a} with 2-3 items; questions must include the keyword where natural).
"""


def _seo_title_fallback(keyword: str, traffic: str) -> str:
    kw = keyword.strip().title()
    extra = f" — Why {kw} Is Trending Now"
    if len(kw) + len(extra) > 65:
        return f"{kw} Trending: What to Know Today | Detailz"[:65]
    return f"{kw}{extra} | Detailz"


def _meta_fallback(keyword: str, traffic: str, news_titles: list[str]) -> str:
    kw = keyword
    hint = news_titles[0][:80] if news_titles else "breaking search interest"
    base = f"{kw} is spiking on Google ({traffic or 'high'} searches). {hint}"
    return re.sub(r"\s+", " ", base)[:160]


def _fallback_paragraphs(item: TrendItem) -> list[str]:
    kw = item.keyword
    paras = [
        f"Search interest for «{kw}» jumped today on Google Trends "
        f"({item.approx_traffic or 'rising'} queries in the United States). "
        f"Detailz breaks down why readers are searching and what news is driving it.",
    ]
    if item.news:
        paras.append(
            f"Coverage points to several developing angles. "
            f"Lead headline: «{item.news[0].title}»"
            + (f" ({item.news[0].source})." if item.news[0].source else ".")
        )
        for n in item.news[1:3]:
            paras.append(
                f"Related reporting: «{n.title}»"
                + (f" via {n.source}." if n.source else ".")
            )
    else:
        paras.append(
            f"Few major headlines were bundled with this trend yet; "
            f"check back as publishers file more stories on {kw}."
        )
    paras.append(
        f"If you searched for {kw}, bookmark this page for context and links to "
        f"the latest updates as the trend evolves."
    )
    return paras


def _h1_fallback(keyword: str) -> str:
    return f"{keyword.strip().title()}: Why It's Trending on Google Today"


def _faq_fallback(keyword: str, traffic: str) -> list[dict[str, str]]:
    kw = keyword
    return [
        {
            "q": f"Why is «{kw}» trending on Google?",
            "a": f"Search volume for «{kw}» rose sharply on Google Trends ({traffic or 'high interest'} in the U.S.), "
            f"usually tied to breaking news or viral moments in the bundled headlines.",
        },
        {
            "q": f"What are people searching for with «{kw}»?",
            "a": f"Readers typically want context on the latest news, timelines, and explainers around «{kw}» "
            f"while the trend is active.",
        },
    ]


def _faq_to_schema(faq: list[dict[str, str]]) -> list[dict]:
    return [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
        }
        for item in faq
        if item.get("q") and item.get("a")
    ]


def _faq_to_html(faq: list[dict[str, str]]) -> str:
    if not faq:
        return ""
    items = "".join(
        f"<h3>{html.escape(f['q'])}</h3><p>{html.escape(f['a'])}</p>" for f in faq if f.get("q")
    )
    return f'<section class="trending-faq" aria-label="FAQ"><h2 id="faq">Frequently asked questions</h2>{items}</section>'


def _paragraphs_to_html(paragraphs: list[str], image_url: str | None, keyword: str) -> str:
    parts = [f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip()]
    if image_url:
        alt = html.escape(f"{keyword} trending on Google")
        parts.insert(
            1,
            f'<figure class="wp-block-image size-large"><img src="{html.escape(image_url, quote=True)}" '
            f'alt="{alt}" loading="eager" decoding="async"></figure>',
        )
    return "\n".join(parts)


def _call_llm(item: TrendItem) -> dict[str, Any]:
    context = {
        "keyword": item.keyword,
        "approx_traffic": item.approx_traffic,
        "traffic_score": item.traffic_score,
        "news": [
            {"title": n.title, "source": n.source, "url": n.url} for n in item.news[:6]
        ],
    }
    body = {
        "model": SETTINGS.openai_model,
        "temperature": 0.45,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": TRENDING_SYSTEM},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    }
    url = f"{SETTINGS.openai_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {SETTINGS.openai_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def build_article(
    item: TrendItem,
    image_url: str | None,
) -> dict[str, Any]:
    news_titles = [n.title for n in item.news]
    if SETTINGS.openai_api_key:
        try:
            data = _call_llm(item)
            title = (data.get("seo_title") or "").strip()
            if item.keyword.lower() not in title.lower():
                title = _seo_title_fallback(item.keyword, item.approx_traffic)
            desc = (data.get("meta_description") or "").strip()
            if item.keyword.lower() not in desc.lower():
                desc = _meta_fallback(item.keyword, item.approx_traffic, news_titles)
            paragraphs = data.get("paragraphs") or _fallback_paragraphs(item)
            h1 = (data.get("h1") or "").strip() or _h1_fallback(item.keyword)
            faq = data.get("faq") or _faq_fallback(item.keyword, item.approx_traffic)
            kw_list = data.get("keywords") or []
        except Exception as exc:
            logger.warning("LLM trending enrich failed: %s", exc)
            title = _seo_title_fallback(item.keyword, item.approx_traffic)
            desc = _meta_fallback(item.keyword, item.approx_traffic, news_titles)
            paragraphs = _fallback_paragraphs(item)
            h1 = _h1_fallback(item.keyword)
            faq = _faq_fallback(item.keyword, item.approx_traffic)
            kw_list = [item.keyword, f"{item.keyword} trending", "google trends"]
    else:
        title = _seo_title_fallback(item.keyword, item.approx_traffic)
        desc = _meta_fallback(item.keyword, item.approx_traffic, news_titles)
        paragraphs = _fallback_paragraphs(item)
        h1 = _h1_fallback(item.keyword)
        faq = _faq_fallback(item.keyword, item.approx_traffic)
        kw_list = [item.keyword, f"{item.keyword} trending", "google trends"]

    if item.keyword.lower() not in h1.lower():
        h1 = _h1_fallback(item.keyword)

    body_html = _paragraphs_to_html(paragraphs, image_url, item.keyword)
    body_html += _faq_to_html(faq)
    sources = [{"title": n.title, "url": n.url, "source": n.source} for n in item.news[:5]]
    if sources:
        links = " ".join(
            f'<a href="{html.escape(s["url"], quote=True)}" rel="noopener noreferrer">'
            f'{html.escape(s["source"] or s["title"])}</a>'
            for s in sources
            if s.get("url")
        )
        body_html += f'<p><strong>Sources:</strong> {links}</p>'

    seo_keywords = ", ".join(dict.fromkeys([item.keyword, *[str(k) for k in kw_list if k]]))[:500]

    return {
        "seo_title": title,
        "h1": h1,
        "meta_description": desc,
        "article_body": body_html,
        "source_links": json.dumps(sources, ensure_ascii=False),
        "faq_json": json.dumps(faq, ensure_ascii=False),
        "seo_keywords": seo_keywords,
    }