from __future__ import annotations



import re



_STOP = frozenset(

    {

        "a",

        "an",

        "the",

        "and",

        "or",

        "for",

        "of",

        "in",

        "on",

        "at",

        "to",

        "vs",

        "v",

        "de",

        "la",

        "el",

    }

)



_CLUSTER_TERMS = (

    "basketball",

    "football",

    "steelers",

    "nfl",

    "nba",

    "ncaa",

    "gta",

    "thanksgiving",

    "treasury",

    "mega",

    "millions",

    "avengers",

    "marvel",

    "disney",

    "state",

    "university",

    "movie",

    "actor",

    "actress",

)





def keyword_tokens(keyword: str) -> set[str]:

    words = re.findall(r"[a-z0-9]+", (keyword or "").lower())

    return {w for w in words if len(w) > 2 and w not in _STOP}





def cluster_tag(keyword: str) -> str | None:

    low = (keyword or "").lower()

    for term in _CLUSTER_TERMS:

        if term in low:

            return term

    tokens = sorted(keyword_tokens(keyword), key=len, reverse=True)

    return tokens[0] if tokens else None





def _link_row(topic: dict, url_for) -> dict:

    return {

        "slug": topic["slug"],

        "keyword": topic.get("keyword") or "",

        "title": topic.get("display_title") or topic.get("h1") or topic.get("keyword") or topic["slug"],

        "url": url_for(f"/{topic['slug']}/"),

    }





def pick_related_topics(

    topic: dict,

    all_topics: list[dict],

    *,

    url_for,

    limit: int = 12,

) -> list[dict]:

    slug = topic["slug"]

    tokens = keyword_tokens(topic.get("keyword") or "")

    cluster = cluster_tag(topic.get("keyword") or "")

    scored: list[tuple[float, dict]] = []



    for t in all_topics:

        if t["slug"] == slug:

            continue

        ot = keyword_tokens(t.get("keyword") or "")

        overlap = len(tokens & ot)

        score = overlap * 4.0

        if cluster and cluster_tag(t.get("keyword") or "") == cluster:

            score += 5.0

        for tok in tokens:

            if tok in (t.get("slug") or ""):

                score += 2.0

        score += min(int(t.get("traffic_score") or 0) / 50000.0, 3.0)

        scored.append((score, t))



    scored.sort(key=lambda x: (-x[0], x[1].get("published_at") or ""))

    picked = [_link_row(t, url_for) for _, t in scored[:limit]]



    if len(picked) < limit:

        seen = {slug, *(p["slug"] for p in picked)}

        for t in all_topics:

            if t["slug"] in seen:

                continue

            picked.append(_link_row(t, url_for))

            seen.add(t["slug"])

            if len(picked) >= limit:

                break

    return picked





def pick_cluster_topics(

    topic: dict,

    all_topics: list[dict],

    *,

    url_for,

    limit: int = 10,

) -> list[dict]:

    cluster = cluster_tag(topic.get("keyword") or "")

    if not cluster:

        return []

    slug = topic["slug"]

    matches = [

        t

        for t in all_topics

        if t["slug"] != slug and cluster_tag(t.get("keyword") or "") == cluster

    ]

    matches.sort(key=lambda t: (-int(t.get("traffic_score") or 0), t.get("published_at") or ""))

    return [_link_row(t, url_for) for t in matches[:limit]]





def pick_topic_tags(

    topic: dict,

    all_topics: list[dict],

    *,

    url_for,

    limit: int = 8,

) -> list[dict]:

    """Link out using overlapping words in other keywords (internal keyword mesh)."""

    slug = topic["slug"]

    tokens = keyword_tokens(topic.get("keyword") or "")

    tags: list[dict] = []

    used: set[str] = set()



    for tok in sorted(tokens, key=len, reverse=True):

        if len(tags) >= limit:

            break

        for t in all_topics:

            if t["slug"] == slug or tok not in (t.get("keyword") or "").lower():

                continue

            if t["slug"] in used:

                continue

            tags.append(

                {

                    "label": tok.replace("-", " ").title(),

                    "url": url_for(f"/{t['slug']}/"),

                    "title": t.get("h1") or t.get("keyword"),

                }

            )

            used.add(t["slug"])

            break

    return tags
