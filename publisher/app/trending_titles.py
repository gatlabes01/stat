from __future__ import annotations

import json
import re

_ACRONYMS = {
    "us", "uk", "uae", "nfl", "nba", "mlb", "nhl", "ncaa", "gta", "tmz", "cia", "fbi",
    "ai", "usa", "utep",
}
_SMALL = {"a", "an", "the", "and", "or", "for", "of", "in", "on", "at", "to", "vs", "v"}


def smart_display(keyword: str) -> str:
    raw = re.sub(r"\s+", " ", (keyword or "").strip())
    if not raw:
        return "This Topic"
    if raw.lower() in ("x men", "x-men"):
        return "X-Men"
    if raw.lower() == "utep basketball":
        return "UTEP Basketball"
    parts = raw.split()
    out: list[str] = []
    for i, w in enumerate(parts):
        low = w.lower()
        if low in _ACRONYMS:
            out.append(w.upper() if len(w) <= 5 else w.title())
        elif low in _SMALL and i > 0:
            out.append(low)
        else:
            out.append(w.capitalize() if w.islower() else w)
    return " ".join(out)


def _news_titles_from_topic(topic: dict) -> list[str]:
    try:
        items = json.loads(topic.get("source_links") or "[]")
        return [str(x["title"]).strip() for x in items if x.get("title")]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def _clean_news_line(title: str) -> str:
    t = re.sub(r"\s+", " ", title.strip())
    t = re.split(r"\s*\|\s*", t)[0]
    return t.strip(" .")


def _short_angle(news_title: str, max_words: int = 9) -> str:
    t = _clean_news_line(news_title)
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;:") + "…"
    return t


def human_seo_title(keyword: str, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    if news_titles:
        angle = _short_angle(news_titles[0], 8)
        base = f"{subj}: {angle}" if len(f"{subj}: {angle}") <= 54 else f"{subj}: {angle[:40].rsplit(' ', 1)[0]}…"
        return f"{base} | Detailz"
    return f"{subj} | Detailz"


def human_h1(keyword: str, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    if news_titles:
        return f"{subj}: {_short_angle(news_titles[0], 10)}"
    return subj


def human_list_title(keyword: str, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    if news_titles:
        return f"{subj}: {_short_angle(news_titles[0], 7)}"
    return subj


def human_meta_description(keyword: str, news_titles: list[str]) -> str:
    if news_titles:
        text = _clean_news_line(news_titles[0])
    else:
        text = f"Coverage and updates on {smart_display(keyword)}."
    return re.sub(r"\s+", " ", text)[:160]


def human_list_deck(keyword: str, news_titles: list[str]) -> str:
    """Hub excerpt: lead headline + optional second angle (not SEO boilerplate)."""
    if not news_titles:
        return f"Reports and updates on {smart_display(keyword)}."
    lead = _clean_news_line(news_titles[0])
    if len(news_titles) > 1:
        extra = _short_angle(news_titles[1], 18)
        text = f"{lead} Also in the mix: {extra}"
    else:
        text = lead
    return re.sub(r"\s+", " ", text)[:300]


def apply_polished_titles(topic: dict) -> dict:
    kw = topic.get("keyword") or ""
    news = _news_titles_from_topic(topic)
    topic["display_title"] = human_list_title(kw, news)
    topic["h1"] = human_h1(kw, news)
    topic["seo_title"] = human_seo_title(kw, news)
    topic["meta_description"] = human_meta_description(kw, news)
    topic["meta_description_short"] = topic["meta_description"][:300]
    topic["list_deck"] = human_list_deck(kw, news)
    return topic