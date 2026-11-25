from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

import httpx

from app.config import SETTINGS
from app.trending_rss import TrendItem
from app.trending_titles import apply_polished_titles, smart_display

logger = logging.getLogger(__name__)

TRENDING_SYSTEM = """You write trending explainers for Detailz like a sharp entertainment/news editor (TMZ-adjacent tone: clear, conversational, not robotic).
Voice: second person sparingly, short sentences, no "spiking on Google" boilerplate, no "Why X Is Trending Now".
seo_title/h1/meta are rewritten on publish — focus on great paragraphs + faq.
- paragraphs: 4-6 vivid but factual graphs using ONLY the bundled headlines. Lead with what happened, then why searchers care.
- Do not invent quotes, stats, or events.
Return JSON: paragraphs, keywords (5-8), faq (2-3 items with q/a in plain English).
"""


def _fallback_paragraphs(item: TrendItem) -> list[str]:
    name = smart_display(item.keyword)
    paras = [
        f"If you typed “{name}” into Google today, you're not alone — "
        f"the phrase is all over Trends ({item.approx_traffic or 'rising'} U.S. interest).",
    ]
    if item.news:
        lead = item.news[0]
        paras.append(
            f"The clearest trigger looks like this headline: “{lead.title}”"
            + (f" ({lead.source})." if lead.source else ".")
        )
        for n in item.news[1:3]:
            paras.append(f"Also in the mix: “{n.title}”" + (f" from {n.source}." if n.source else "."))
    else:
        paras.append("No single headline is attached yet — the spike may be pure curiosity or early news still landing.")
    paras.append(
        f"Below is a quick, readable breakdown of what searchers usually want when {name} trends, "
        f"plus answers to common questions."
    )
    return paras


def _faq_fallback(keyword: str, traffic: str) -> list[dict[str, str]]:
    name = smart_display(keyword)
    return [
        {
            "q": f"Why is {name} trending?",
            "a": f"Google Trends shows a sharp jump in U.S. searches for “{name}” ({traffic or 'rising'}), "
            f"usually tied to the news stories bundled with this spike.",
        },
        {
            "q": f"What do people want to know about {name}?",
            "a": f"Mostly the latest headlines, quick context, and whether something bigger is coming — "
            f"not long-winded trend jargon.",
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
            paragraphs = data.get("paragraphs") or _fallback_paragraphs(item)
            faq = data.get("faq") or _faq_fallback(item.keyword, item.approx_traffic)
            kw_list = data.get("keywords") or []
        except Exception as exc:
            logger.warning("LLM trending enrich failed: %s", exc)
            paragraphs = _fallback_paragraphs(item)
            faq = _faq_fallback(item.keyword, item.approx_traffic)
            kw_list = [item.keyword, f"{item.keyword} trending", "google trends"]
    else:
        paragraphs = _fallback_paragraphs(item)
        faq = _faq_fallback(item.keyword, item.approx_traffic)
        kw_list = [item.keyword, f"{item.keyword} trending", "google trends"]

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

    out = {
        "seo_title": "",
        "h1": "",
        "meta_description": "",
        "article_body": body_html,
        "source_links": json.dumps(sources, ensure_ascii=False),
        "faq_json": json.dumps(faq, ensure_ascii=False),
        "seo_keywords": seo_keywords,
        "keyword": item.keyword,
        "approx_traffic": item.approx_traffic,
    }
    return apply_polished_titles(out)