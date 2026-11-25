from __future__ import annotations

import json
import re

_ACRONYMS = {
    "us", "uk", "uae", "nfl", "nba", "mlb", "nhl", "ncaa", "gta", "tmz", "cia", "fbi",
    "ai", "usa", "nfl",
}
_SMALL = {"a", "an", "the", "and", "or", "for", "of", "in", "on", "at", "to", "vs", "v"}


def smart_display(keyword: str) -> str:
    raw = re.sub(r"\s+", " ", (keyword or "").strip())
    if not raw:
        return "This Topic"
    if raw.lower() in ("x men", "x-men"):
        return "X-Men"
    parts = raw.split()
    out: list[str] = []
    for i, w in enumerate(parts):
        low = w.lower()
        if low in _ACRONYMS and len(w) <= 4:
            out.append(low.upper())
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
    t = re.sub(r"\s*[-–—]\s*", " — ", t)
    return t.strip(" .")


def _short_angle(news_title: str, max_words: int = 9) -> str:
    t = _clean_news_line(news_title)
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;:")
        if not t.endswith("…"):
            t += "…"
    return t


def format_traffic_human(traffic: str | None) -> str:
    if not traffic:
        return "all of a sudden"
    t = traffic.strip()
    if re.match(r"^\d+\+$", t.replace(",", "")):
        n = int(t.rstrip("+").replace(",", ""))
        if n >= 50_000:
            return "by the tens of thousands"
        if n >= 5_000:
            return "by the thousands"
        if n >= 500:
            return "in a big way"
        return "fast"
    return "in a big way"


def human_seo_title(keyword: str, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    if news_titles:
        angle = _short_angle(news_titles[0], 8)
        # Read like a newsroom hed, not a template
        candidates = [
            f"{subj}: {angle}",
            f"Everyone’s Googling {subj} After {angle}",
            f"{angle} — Why {subj} Is All Over Google",
        ]
        for c in candidates:
            base = c if len(c) <= 54 else f"{subj} Is Trending — {angle}"[:54]
            title = f"{base} | Detailz"
            if len(title) <= 70:
                return title
        return f"{subj} Trending Today | Detailz"
    return f"{subj} Is Suddenly Everywhere on Google | Detailz"


def human_h1(keyword: str, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    if news_titles:
        angle = _short_angle(news_titles[0], 7)
        return f"Why {subj} is blowing up on Google ({angle})"
    return f"Why is everyone searching for {subj} today?"


def human_list_title(keyword: str, news_titles: list[str]) -> str:
    """Hub list link — short, no brand."""
    subj = smart_display(keyword)
    if news_titles:
        angle = _short_angle(news_titles[0], 6)
        return f"{subj}: {angle}"
    return f"{subj} is trending right now"


def human_meta_description(keyword: str, traffic: str | None, news_titles: list[str]) -> str:
    subj = smart_display(keyword)
    pace = format_traffic_human(traffic)
    if news_titles:
        lead = _short_angle(news_titles[0], 12)
        text = (
            f"Searches for {subj} jumped {pace} after fresh headlines — including "
            f"“{lead}.” Quick read on what people want to know."
        )
    else:
        text = (
            f"{subj} is climbing on Google Trends {pace}. "
            f"We summarize why people are searching and what to watch next."
        )
    return re.sub(r"\s+", " ", text)[:160]


def apply_polished_titles(topic: dict) -> dict:
    """Human-readable titles on every export (overrides robotic DB/LLM strings)."""
    kw = topic.get("keyword") or ""
    traffic = topic.get("approx_traffic")
    news = _news_titles_from_topic(topic)

    topic["display_title"] = human_list_title(kw, news)
    topic["h1"] = human_h1(kw, news)
    topic["seo_title"] = human_seo_title(kw, news)
    topic["meta_description"] = human_meta_description(kw, traffic, news)
    topic["meta_description_short"] = topic["meta_description"][:300]
    return topic