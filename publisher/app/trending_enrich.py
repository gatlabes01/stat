from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

import httpx

from app.config import SETTINGS
from app.trending_rss import TrendItem, TrendNewsItem
from app.trending_titles import apply_polished_titles, smart_display
from app.voice import voice_prompt_section

logger = logging.getLogger(__name__)

TARGET_WORDS = 300
TARGET_MIN = 260
TARGET_MAX = 340

def trending_system_prompt() -> str:
    return f"""You write ~{TARGET_WORDS}-word news copy for Detailz about the given topic.

{voice_prompt_section()}

Rules:
- Detailz voice: skeptical-but-fair, plain English, short leads — not wire-service flat or self-help.
- Use ONLY facts from the provided headlines — no invented quotes, scores, dates, or drama.
- Weave 0–2 signature voice hooks where they fit naturally.
- Never mention Google, search volume, trending, spiking, AI, briefings, explainers, or "what to watch next".
- Banned phrases: plain-English, rundown, news cycle, catch up quickly, smart move, traction, puzzle pieces.
- Use the display keyword exactly 2 or 3 times in paragraphs only (not FAQ).
- Word count {TARGET_MIN}–{TARGET_MAX} across paragraphs.
Return JSON:
  paragraphs: array of 5-8 strings (one paragraph each),
  keywords: 5-8 related lowercase phrases,
  faq: optional 2 short Q&As tied to the reporting (not meta/SEO questions).
"""


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _keyword_label(keyword: str) -> str:
    return smart_display(keyword)


def count_keyword_mentions(paragraphs: list[str], keyword: str) -> int:
    name = _keyword_label(keyword)
    blob = " ".join(paragraphs)
    raw = (keyword or "").strip()
    n = len(re.findall(re.escape(name), blob, flags=re.IGNORECASE))
    if raw and raw.lower() != name.lower():
        n += len(re.findall(re.escape(raw), blob, flags=re.IGNORECASE))
    return n


def trim_keyword_mentions(paragraphs: list[str], keyword: str, maximum: int = 3) -> list[str]:
    name = _keyword_label(keyword)
    excess = count_keyword_mentions(paragraphs, keyword) - maximum
    if excess <= 0:
        return paragraphs
    out: list[str] = []
    for p in paragraphs:
        if excess <= 0:
            out.append(p)
            continue
        hits = len(re.findall(re.escape(name), p, flags=re.IGNORECASE))
        if hits == 0 and keyword.lower() != name.lower():
            hits = len(re.findall(re.escape(keyword), p, flags=re.IGNORECASE))
        while excess > 0 and hits > 0:
            p = re.sub(re.escape(name), "the story", p, count=1, flags=re.IGNORECASE)
            if keyword.lower() != name.lower():
                p = re.sub(re.escape(keyword), "the story", p, count=1, flags=re.IGNORECASE)
            excess -= 1
            hits -= 1
        out.append(p)
    return out


def add_keyword_mentions(paragraphs: list[str], keyword: str, minimum: int = 2) -> list[str]:
    need = minimum - count_keyword_mentions(paragraphs, keyword)
    if need <= 0:
        return paragraphs
    name = _keyword_label(keyword)
    inserts = [
        f"Reports on {name} line up on the same facts, even when the headlines differ.",
        f"Coverage of {name} has picked up across sports and news desks in the last day.",
    ]
    result = list(paragraphs)
    pos = min(1, len(result))
    for line in inserts[:need]:
        result.insert(pos, line)
        pos += 2
    return result


def enforce_keyword_density(paragraphs: list[str], keyword: str) -> list[str]:
    paragraphs = trim_keyword_mentions(paragraphs, keyword, maximum=3)
    paragraphs = add_keyword_mentions(paragraphs, keyword, minimum=2)
    paragraphs = trim_keyword_mentions(paragraphs, keyword, maximum=3)
    return paragraphs


def _strip_google_jargon(text: str) -> str:
    bad = (
        r"\b(spiking on google|google trends|search volume|people are searching|"
        r"trending on google|jumped on google|u\.s\. searches)\b"
    )
    return re.sub(bad, "", text, flags=re.I)


def _fallback_paragraphs(item: TrendItem) -> list[str]:
    name = _keyword_label(item.keyword)
    paras: list[str] = []

    if item.news:
        lead = item.news[0]
        paras.append(
            f"{name} drew fresh coverage after this report: "
            f"“{_strip_google_jargon(lead.title)}.”"
            + (f" ({lead.source})" if lead.source else "")
        )
        paras.append(
            "Follow-up pieces usually hinge on one new detail — a score, a filing, an injury update, "
            "or a quote from someone involved."
        )
        templates = (
            "{label} also ran: “{t}.”",
            "From {label}: “{t}.”",
            "Another report: “{t}.” ({label})",
        )
        for i, n in enumerate(item.news[1:4]):
            if not n.title:
                continue
            label = n.source or "Elsewhere"
            t = templates[i % len(templates)].format(
                t=_strip_google_jargon(n.title), label=label
            )
            paras.append(t)
    else:
        paras.append(f"Major outlets had not filed a lead story on {name} at publish time.")
        paras.append(
            "When the first report lands, expect sports, politics, or entertainment desks "
            "to pick it up depending on the topic."
        )

    paras.append(
        "The links below are the same headlines summarized here — use them for full context "
        "and attribution."
    )
    paras.append(
        f"Across those pieces, {name} shows up where the facts overlap, not as a separate "
        "narrative in every outlet."
    )

    fillers = [
        (
            "Editors often tighten the story after the first push, when principals comment "
            "or league or agency sources weigh in."
        ),
        (
            "Confirmed details and anonymous tips travel at different speeds; "
            "treat single-source items accordingly."
        ),
        (
            "When two or more outlets match on the same fact, that detail usually holds."
        ),
        (
            "Late updates can reverse an earlier line — check timestamps on the source stories."
        ),
    ]
    fi = 0
    while _word_count(" ".join(paras)) < TARGET_MIN and fi < len(fillers):
        paras.append(fillers[fi])
        fi += 1

    paras = [_strip_google_jargon(p) for p in paras if p.strip()]
    return enforce_keyword_density(paras, item.keyword)


def _faq_fallback(keyword: str) -> list[dict[str, str]]:
    return [
        {
            "q": "What are outlets reporting?",
            "a": "See the source links above for the full headlines and reporting.",
        },
        {
            "q": "Could this change?",
            "a": "Yes — new statements or filings often shift how the story is framed.",
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
    return f'<section class="trending-faq" aria-label="FAQ"><h2 id="faq">Background</h2>{items}</section>'


def _paragraphs_to_html(paragraphs: list[str], image_url: str | None, keyword: str) -> str:
    name = smart_display(keyword)
    parts = [f"<p>{html.escape(_strip_google_jargon(p))}</p>" for p in paragraphs if p.strip()]
    if image_url:
        alt = html.escape(f"{name} — news photo")
        parts.insert(
            1,
            f'<figure class="wp-block-image size-large"><img src="{html.escape(image_url, quote=True)}" '
            f'alt="{alt}" loading="eager" decoding="async"></figure>',
        )
    return "\n".join(parts)


def _call_llm(item: TrendItem) -> dict[str, Any]:
    context = {
        "keyword": item.keyword,
        "display_name": smart_display(item.keyword),
        "news": [{"title": n.title, "source": n.source, "url": n.url} for n in item.news[:8]],
        "target_words": TARGET_WORDS,
    }
    body = {
        "model": SETTINGS.openai_model,
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": trending_system_prompt()},
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


def compose_article_html(item: TrendItem, image_url: str | None) -> tuple[str, list[dict], list[str]]:
    if SETTINGS.openai_api_key:
        try:
            data = _call_llm(item)
            paragraphs = data.get("paragraphs") or _fallback_paragraphs(item)
            faq = data.get("faq") or _faq_fallback(item.keyword)
            kw_list = data.get("keywords") or []
        except Exception as exc:
            logger.warning("LLM trending enrich failed: %s", exc)
            paragraphs = _fallback_paragraphs(item)
            faq = _faq_fallback(item.keyword)
            kw_list = []
    else:
        paragraphs = _fallback_paragraphs(item)
        faq = _faq_fallback(item.keyword)
        kw_list = []

    paragraphs = enforce_keyword_density(paragraphs, item.keyword)
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
        body_html += f'<p class="trending-sources"><strong>Sources:</strong> {links}</p>'
    return body_html, faq, kw_list


def topic_to_trend_item(topic: dict) -> TrendItem:
    news: list[TrendNewsItem] = []
    try:
        for s in json.loads(topic.get("source_links") or "[]"):
            news.append(
                TrendNewsItem(
                    title=s.get("title") or "",
                    url=s.get("url") or "",
                    source=s.get("source") or "",
                    picture="",
                )
            )
    except json.JSONDecodeError:
        pass
    return TrendItem(
        keyword=topic.get("keyword") or "",
        approx_traffic=topic.get("approx_traffic") or "",
        traffic_score=int(topic.get("traffic_score") or 0),
        pub_date=topic.get("trend_pub_date") or "",
        picture=topic.get("image_url") or "",
        picture_source="",
        news=news,
    )


def refresh_topic_body(topic: dict) -> dict:
    """Rebuild ~300-word body from stored keyword + sources (runs on every export)."""
    item = topic_to_trend_item(topic)
    img = topic.get("image_url")
    body_html, faq, kw_list = compose_article_html(item, img)
    topic["article_body"] = body_html
    topic["faq_json"] = json.dumps(faq, ensure_ascii=False)
    topic["faq_schema"] = _faq_to_schema(faq)
    extra = ", ".join(kw_list) if kw_list else ""
    topic["seo_keywords"] = ", ".join(
        dict.fromkeys([topic.get("keyword") or "", *(extra.split(", ") if extra else [])])
    )[:500]
    return topic


def build_article(item: TrendItem, image_url: str | None) -> dict[str, Any]:
    body_html, faq, kw_list = compose_article_html(item, image_url)
    seo_keywords = ", ".join(dict.fromkeys([item.keyword, *[str(k) for k in kw_list if k]]))[:500]
    out = {
        "seo_title": "",
        "h1": "",
        "meta_description": "",
        "article_body": body_html,
        "source_links": json.dumps(
            [{"title": n.title, "url": n.url, "source": n.source} for n in item.news[:5]],
            ensure_ascii=False,
        ),
        "faq_json": json.dumps(faq, ensure_ascii=False),
        "seo_keywords": seo_keywords,
        "keyword": item.keyword,
        "approx_traffic": item.approx_traffic,
    }
    return apply_polished_titles(out)