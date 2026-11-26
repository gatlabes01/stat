from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import SETTINGS
from app.paths import project_root
from app.format_dates import format_story_date, to_iso8601
from app import trending_db as tdb
from app.seo_ping import ensure_indexnow_key_file
from app.sync import COPYRIGHT_NOTICE
from app.trending_enrich import _faq_fallback, _faq_to_schema, refresh_topic_body
from app.trending_links import pick_cluster_topics, pick_related_topics, pick_topic_tags
from app.trending_titles import apply_polished_titles
def export_root() -> Path:
    import os

    root = project_root()
    raw = os.environ.get("EXPORT_DIR")
    return Path(raw) if raw else root


def trending_root_dir(out: Path | None = None) -> Path:
    base = out or export_root()
    seg = SETTINGS.trending_base_path.lstrip("/") or "trending"
    return base / seg


def _url_for(path: str) -> str:
    base = SETTINGS.trending_base_path.rstrip("/")
    if path in ("", "/"):
        return f"{base}/"
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith(f"{base}/") or path == base:
        return path
    return f"{base}{path}"


def _abs_url(path: str) -> str:
    return f"{SETTINGS.site_url.rstrip('/')}{_url_for(path)}"


def _rewrite_body(html: str) -> str:
    if not html:
        return html
    tb = SETTINGS.trending_base_path.rstrip("/")
    html = html.replace('src="/trending/media/', f'src="{tb}/media/')
    if SETTINGS.site_url.startswith("http"):
        html = re.sub(
            rf'src="{re.escape(tb)}/media/([^"]+)"',
            lambda m: f'src="{_abs_url("/media/" + m.group(1))}"',
            html,
        )
    return html


_SKIP_TOPIC_DIRS = frozenset({"archive", "media", "static", "articles"})


def _title_from_disk_index(index_html: Path) -> str:
    try:
        html = index_html.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            return m.group(1).split("|")[0].strip()
    except OSError:
        pass
    return index_html.parent.name.replace("-", " ").title()


def _ensure_topic_thumb(topic: dict, media_src: Path) -> None:
    if topic.get("image_url"):
        return
    slug = topic.get("slug") or ""
    if not slug:
        return
    for name in ("01.png", "01.jpg", "02.jpg", "02.png"):
        if (media_src / slug / name).is_file():
            topic["image_url"] = _url_for(f"/media/{slug}/{name}")
            topic["image_url_abs"] = f"{SETTINGS.site_url.rstrip('/')}{topic['image_url']}"
            return


def _topics_on_disk(trend_out: Path, known_slugs: set[str]) -> list[dict]:
    """Include existing /trending/{slug}/ pages in hub, feed, and sitemap even if missing from DB."""
    extras: list[dict] = []
    for child in trend_out.iterdir():
        if not child.is_dir() or child.name in _SKIP_TOPIC_DIRS or child.name in known_slugs:
            continue
        idx = child / "index.html"
        if not idx.is_file():
            continue
        title = _title_from_disk_index(idx)
        ts = datetime.fromtimestamp(idx.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"
        )
        extras.append(
            {
                "slug": child.name,
                "keyword": child.name.replace("-", " "),
                "h1": title,
                "display_title": title,
                "meta_description": "",
                "published_at": ts,
                "published_label": format_story_date(ts),
                "published_iso": to_iso8601(ts),
            }
        )
    return extras


def _ensure_sitemap_index_entry(repo_root: Path, lastmod: str) -> None:
    loc = f"{SETTINGS.site_url.rstrip('/')}/trending/sitemap.xml"
    for name in ("sitemap_index.xml", "sitemap.xml"):
        path = repo_root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "trending/sitemap.xml" in text:
            continue
        entry = (
            f"\t<sitemap>\n\t\t<loc>{loc}</loc>\n\t\t<lastmod>{lastmod}</lastmod>\n\t</sitemap>\n"
        )
        text = text.replace("</sitemapindex>", entry + "</sitemapindex>")
        path.write_text(text, encoding="utf-8")


def export_trending_site(export_dir: Path | None = None) -> dict:
    out = export_dir or export_root()
    trend_out = trending_root_dir(out)
    repo_root = export_root()

    conn = tdb.connect()
    tdb.init_db(conn)
    rows = tdb.published_topics(conn)
    slugs = tdb.all_published(conn)
    conn.close()

    env = Environment(
        loader=FileSystemLoader(project_root() / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals.update(
        {
            "site_name": SETTINGS.site_name,
            "site_url": SETTINGS.site_url,
            "trending_base_path": SETTINGS.trending_base_path,
            "url_for": _url_for,
            "abs_url": _abs_url,
            "copyright_notice": COPYRIGHT_NOTICE,
            "google_site_verification": SETTINGS.google_site_verification,
        }
    )

    article_tpl = env.get_template("export/trending_article.html")
    index_tpl = env.get_template("export/trending_index.html")
    feed_tpl = env.get_template("export/trending_feed.xml")

    legacy_articles = trend_out / "articles"
    if legacy_articles.exists():
        shutil.rmtree(legacy_articles, ignore_errors=True)

    stories_for_index: list[dict] = []
    for row in rows:
        topic = dict(row)
        topic = refresh_topic_body(topic)
        topic["article_body"] = _rewrite_body(topic.get("article_body") or "")
        slug = topic["slug"]
        dest = trend_out / slug
        dest.mkdir(parents=True, exist_ok=True)
        canonical = _abs_url(f"/{slug}/")
        img = topic.get("image_url") or ""
        if img.startswith("http"):
            topic["image_url_abs"] = img
        elif img:
            topic["image_url"] = _url_for(img) if not img.startswith(SETTINGS.trending_base_path) else img
            topic["image_url_abs"] = f"{SETTINGS.site_url.rstrip('/')}{topic['image_url']}"
        else:
            topic["image_url_abs"] = ""
        topic["published_label"] = format_story_date(topic.get("published_at"))
        topic["published_iso"] = to_iso8601(topic.get("published_at"))
        apply_polished_titles(topic)
        try:
            faq_raw = json.loads(topic.get("faq_json") or "[]")
        except json.JSONDecodeError:
            faq_raw = []
        if not faq_raw:
            faq_raw = _faq_fallback(topic["keyword"], topic.get("approx_traffic") or "")
        topic["faq_schema"] = _faq_to_schema(faq_raw)
        topic["modified_iso"] = topic["published_iso"]

        stories_for_index.append(topic)

    known = {t["slug"] for t in stories_for_index}
    stories_for_index.extend(_topics_on_disk(trend_out, known))
    stories_for_index.sort(
        key=lambda t: (t.get("published_at") or t.get("created_at") or ""),
        reverse=True,
    )

    media_src = project_root() / "data" / "trending_media"
    for topic in stories_for_index:
        _ensure_topic_thumb(topic, media_src)

    # Second pass: add related links now that index list is built
    for topic in stories_for_index:
        slug = topic["slug"]
        dest = trend_out / slug
        related = pick_related_topics(topic, stories_for_index, url_for=_url_for, limit=12)
        cluster = pick_cluster_topics(topic, stories_for_index, url_for=_url_for, limit=10)
        tag_links = pick_topic_tags(topic, stories_for_index, url_for=_url_for, limit=8)
        latest_topics = [
            {
                "slug": s["slug"],
                "title": s.get("display_title") or s.get("h1") or s["keyword"],
                "url": _url_for(f"/{s['slug']}/"),
            }
            for s in stories_for_index
            if s["slug"] != slug
        ][:8]
        canonical = _abs_url(f"/{slug}/")
        (dest / "index.html").write_text(
            article_tpl.render(
                topic=topic,
                canonical=canonical,
                related_topics=related,
                cluster_topics=cluster,
                tag_links=tag_links,
                latest_topics=latest_topics,
                trending_hub_url=_abs_url("/"),
            ),
            encoding="utf-8",
        )

    item_list = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "url": _abs_url(f"/{t['slug']}/"),
            "name": t.get("display_title") or t.get("h1") or t["keyword"],
        }
        for i, t in enumerate(stories_for_index[:100])
    ]

    (trend_out / "index.html").write_text(
        index_tpl.render(topics=stories_for_index, total=len(stories_for_index), item_list=item_list),
        encoding="utf-8",
    )

    (trend_out / "feed.xml").write_text(
        feed_tpl.render(topics=stories_for_index),
        encoding="utf-8",
    )

    lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{_abs_url('/')}</loc><lastmod>{lastmod}</lastmod>"
        f"<changefreq>hourly</changefreq><priority>1.0</priority></url>",
    ]
    published_by_slug = {slug: published_at for slug, published_at in slugs}
    for topic in stories_for_index:
        slug = topic["slug"]
        published_at = published_by_slug.get(slug) or topic.get("published_at") or ""
        loc = _abs_url(f"/{slug}/")
        lm = (published_at or lastmod)[:10]
        sitemap_lines.append(
            f"  <url><loc>{loc}</loc><lastmod>{lm}</lastmod>"
            f"<changefreq>daily</changefreq><priority>0.85</priority></url>"
        )
    sitemap_lines.append("</urlset>")
    (trend_out / "sitemap.xml").write_text("\n".join(sitemap_lines) + "\n", encoding="utf-8")

    (trend_out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        f"Sitemap: {_abs_url('/sitemap.xml')}\n",
        encoding="utf-8",
    )

    ensure_indexnow_key_file(repo_root, SETTINGS.indexnow_key)

    media_src = project_root() / "data" / "trending_media"
    media_dest = trend_out / "media"
    media_dest.mkdir(parents=True, exist_ok=True)
    if media_src.exists():
        for slug_dir in media_src.iterdir():
            if not slug_dir.is_dir():
                continue
            target = media_dest / slug_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(slug_dir, target)

    static_src = project_root() / "static"
    if static_src.exists():
        dest_static = trend_out / "static"
        if dest_static.exists():
            shutil.rmtree(dest_static)
        shutil.copytree(static_src, dest_static)
        news_css = static_src / "news.css"
        if news_css.exists():
            news_static = export_root() / "news" / "static"
            news_static.mkdir(parents=True, exist_ok=True)
            shutil.copy2(news_css, news_static / "news.css")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (trend_out / "publish-meta.json").write_text(
        json.dumps(
            {
                "generated_at": generated,
                "article_count": len(stories_for_index),
                "site_url": SETTINGS.site_url,
                "trending_path": SETTINGS.trending_base_path,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _ensure_sitemap_index_entry(repo_root, lastmod)

    return {
        "export_dir": str(trend_out),
        "articles": len(stories_for_index),
        "generated_at": generated,
        "trending_url": _abs_url("/"),
    }