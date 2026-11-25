from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.compose import compose_tmz_html
from app.config import SETTINGS
from app.database import connect, get_story_by_id
from app.images import cache_story_images
from app.slug import unique_slug
from app.tmz_parse import parse_tmz_article
from app.voice import voice_prompt_section

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You rewrite TMZ article body text for Detailz using the site's personal voice.

{voice_prompt_section()}

Rules:
- Do NOT change the headline or description (they are set separately from TMZ).
- Keep every fact, quote, name, date, and event; same paragraph count and order.
- Rewrite for originality and Detailz voice — not a light word-swap.
- Use 0–2 signature hooks from the voice bible where they fit naturally.
- Do not invent quotes, events, or facts beyond the source.
Return valid JSON only:
- paragraphs: array of strings, one per input paragraph (same count)
- image_alts: optional short alts, one per image
- keywords: optional 5-8 lowercase phrases from the story
"""


def _truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _tmz_title(row, parsed) -> str:
    if parsed and parsed.headline:
        return parsed.headline.strip()
    return (row["title"] or row["source_title"] or "").strip()


def _tmz_description(row, parsed, title: str) -> str:
    raw = row["summary"] or ""
    if raw:
        return _truncate(_strip_html(raw), 320)
    if parsed and parsed.paragraphs:
        return _truncate(parsed.paragraphs[0], 320)
    return title


def _light_touch(paragraphs: list[str]) -> list[str]:
    """No API: keep TMZ wording, normalize spacing only."""
    out: list[str] = []
    for p in paragraphs:
        p = re.sub(r"\s+", " ", p).strip()
        if p and not p.endswith((".", "!", "?")):
            p += "."
        out.append(p)
    return out


def _call_llm(paragraphs: list[str], image_count: int) -> dict[str, Any]:
    if not SETTINGS.openai_api_key:
        return {"paragraphs": _light_touch(paragraphs), "image_alts": [], "keywords": []}

    payload = {
        "paragraphs": paragraphs,
        "image_count": image_count,
        "instruction": "Detailz voice rewrite; preserve all facts and paragraph count.",
    }
    body = {
        "model": SETTINGS.openai_model,
        "temperature": 0.45,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
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
    data = json.loads(content)
    out = data.get("paragraphs") or []
    if len(out) != len(paragraphs):
        data["paragraphs"] = _light_touch(paragraphs)
    return data


def _needs_reenrich(row) -> bool:
    body = row["article_body"] or ""
    seo = row["seo_title"] or ""
    if seo.endswith("| Detailz"):
        return True
    if "Here's the latest:" in body or "Breaking it down:" in body:
        return True
    if row["meta_description"] and seo != (row["source_title"] or row["title"]):
        pass
    return False


def _is_complete(row) -> bool:
    if row["status"] != "published" or not row["article_body"]:
        return False
    if row["images_json"] is None:
        return False
    try:
        imgs = json.loads(row["images_json"])
    except json.JSONDecodeError:
        return False
    if imgs and "article-photo" not in (row["article_body"] or ""):
        return False
    if _needs_reenrich(row):
        return False
    tmz_title = row["source_title"] or row["title"]
    if tmz_title and row["seo_title"] and row["seo_title"].strip() != tmz_title.strip():
        return False
    return True


def enrich_story_record(story_id: int) -> str:
    conn = connect()
    row = get_story_by_id(conn, story_id)
    if not row:
        conn.close()
        return "skipped"
    if _is_complete(row):
        conn.close()
        return "skipped"

    parsed = parse_tmz_article(row["link"])
    tmz_title = _tmz_title(row, parsed)
    meta_description = _tmz_description(row, parsed, tmz_title)

    if not parsed:
        parsed_paras = [_strip_html(row["summary"] or tmz_title)]
        images_meta: list[dict] = []
        layout: list[tuple[int, int]] = []
        if row["image_url"]:
            images_meta = [{"url": row["image_url"], "credit": None, "alt": tmz_title}]
            layout = [(0, 0)]
    else:
        parsed_paras = parsed.paragraphs
        images_meta = [
            {"url": img.url, "credit": img.credit, "alt": tmz_title}
            for img in parsed.images
        ]
        layout = parsed.image_after_paragraph

    slug = row["slug"] or unique_slug(conn, tmz_title)

    try:
        result = _call_llm(parsed_paras, len(images_meta))
        body_paras = result.get("paragraphs") or _light_touch(parsed_paras)

        for i, img in enumerate(images_meta):
            alts = result.get("image_alts") or []
            img["alt"] = alts[i] if i < len(alts) else tmz_title

        cached = cache_story_images(slug, images_meta)
        if not cached and images_meta:
            cached = [{**img, "local_url": img["url"], "cached": False} for img in images_meta]

        article_body = compose_tmz_html(body_paras, cached, layout)
        hero = (cached[0].get("local_url") if cached else None) or (
            images_meta[0]["url"] if images_meta else row["image_url"]
        )

        words = re.findall(r"[a-z]{4,}", tmz_title.lower())
        keywords = ", ".join(
            result.get("keywords")
            or list(dict.fromkeys(words[:6] + ["celebrity news", "entertainment"]))
        )

        conn.execute(
            """
            UPDATE stories SET
                slug = ?,
                title = ?,
                seo_title = ?,
                meta_description = ?,
                keywords = ?,
                article_body = ?,
                images_json = ?,
                image_alt = ?,
                image_url = COALESCE(?, image_url),
                source_title = ?,
                status = 'published',
                enriched_at = datetime('now'),
                error_message = NULL
            WHERE id = ?
            """,
            (
                slug,
                tmz_title,
                tmz_title,
                meta_description,
                keywords,
                article_body,
                json.dumps(cached),
                tmz_title,
                hero,
                tmz_title,
                story_id,
            ),
        )
        conn.commit()
        conn.close()
        return "published"
    except Exception as exc:
        logger.exception("Enrich failed for story %s", story_id)
        conn.execute(
            """
            UPDATE stories SET status = 'failed', error_message = ?, enriched_at = datetime('now')
            WHERE id = ?
            """,
            (str(exc)[:500], story_id),
        )
        conn.commit()
        conn.close()
        return "failed"


def enrich_pending(limit: int | None = None) -> dict[str, int]:
    from app.database import connect as db_connect, ids_needing_enrichment, init_db

    batch = limit if limit is not None else SETTINGS.enrich_batch_size
    conn = db_connect()
    init_db(conn)
    story_ids = ids_needing_enrichment(conn, batch)
    conn.close()

    ok = 0
    failed = 0
    for story_id in story_ids:
        outcome = enrich_story_record(story_id)
        if outcome == "published":
            ok += 1
        elif outcome == "failed":
            failed += 1
    return {"enriched": ok, "failed": failed, "attempted": len(story_ids)}


def mark_stories_for_reenrich(*, all_published: bool = False) -> int:
    conn = connect()
    if all_published:
        cur = conn.execute(
            """
            UPDATE stories SET status = 'pending'
            WHERE status = 'published'
            """
        )
    else:
        cur = conn.execute(
            """
            UPDATE stories SET status = 'pending'
            WHERE status = 'published'
              AND (
                seo_title LIKE '%| Detailz'
                OR article_body LIKE '%Here''s the latest:%'
                OR seo_title != source_title
              )
            """
        )
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n