from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import database as db
from app.config import SETTINGS
from app.paths import project_root
from app.format_dates import format_story_date, to_iso8601
from app.seo_ping import ensure_indexnow_key_file
from app.sync import COPYRIGHT_NOTICE

TEMPLATES = project_root() / "templates"


def export_root() -> Path:
    raw = os.environ.get("EXPORT_DIR")
    root = project_root()
    return Path(raw) if raw else root / "site"


def _news_segment() -> str:
    return SETTINGS.news_base_path.lstrip("/") or "news"


def news_root_dir(out: Path | None = None) -> Path:
    base = out or export_root()
    return base / _news_segment()


def _url_for(path: str) -> str:
    """Paths under the news section only (e.g. /news/article/foo/)."""
    nb = SETTINGS.news_base_path.rstrip("/")
    if path in ("", "/"):
        return f"{nb}/"
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith(f"{nb}/") or path == nb:
        return path
    legacy = (SETTINGS.site_base_path or "").rstrip("/")
    if legacy and path.startswith(f"{legacy}/"):
        return path
    return f"{nb}{path}"


def _abs_url(path: str) -> str:
    return f"{SETTINGS.site_url.rstrip('/')}{_url_for(path)}"


def _rewrite_body(html: str) -> str:
    if not html:
        return html
    nb = SETTINGS.news_base_path.rstrip("/")
    html = html.replace('src="/media/', f'src="{nb}/media/')
    html = html.replace('src="/static/', f'src="{nb}/static/')
    legacy = (SETTINGS.site_base_path or "").rstrip("/")
    if legacy:
        html = html.replace('src="/media/', f'src="{legacy}/media/')
    if SETTINGS.site_url.startswith("http"):
        html = re.sub(
            rf'src="{re.escape(nb)}/media/([^"]+)"',
            lambda m: f'src="{_abs_url("/media/" + m.group(1))}"',
            html,
        )
    return html


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def export_static_site(export_dir: Path | None = None) -> dict:
    """Export TMZ articles under site/news/ (or NEWS_BASE_PATH). Does not touch site root."""
    out = export_dir or export_root()
    out.mkdir(parents=True, exist_ok=True)
    news_out = news_root_dir(out)

    conn = db.connect()
    db.init_db(conn)
    stories = conn.execute(
        """
        SELECT * FROM stories
        WHERE status = 'published' AND article_body IS NOT NULL AND slug IS NOT NULL
        ORDER BY published_at DESC, id DESC
        """
    ).fetchall()
    slugs = db.all_published_slugs(conn)
    conn.close()

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals.update(
        {
            "site_name": SETTINGS.site_name,
            "site_url": SETTINGS.site_url,
            "site_base_path": SETTINGS.site_base_path,
            "news_base_path": SETTINGS.news_base_path,
            "url_for": _url_for,
            "abs_url": _abs_url,
            "copyright_notice": COPYRIGHT_NOTICE,
            "google_site_verification": SETTINGS.google_site_verification,
        }
    )

    article_tpl = env.get_template("export/article.html")
    index_tpl = env.get_template("export/index.html")
    feed_tpl = env.get_template("export/feed.xml")

    news_out.mkdir(parents=True, exist_ok=True)
    articles_root = news_out / "article"
    articles_root.mkdir(parents=True, exist_ok=True)

    live_slugs = {dict(row)["slug"] for row in stories}
    for child in articles_root.iterdir():
        if child.is_dir() and child.name not in live_slugs:
            shutil.rmtree(child, ignore_errors=True)

    for row in stories:
        story = dict(row)
        story["article_body"] = _rewrite_body(story.get("article_body") or "")
        slug = story["slug"]
        dest = articles_root / slug
        dest.mkdir(parents=True, exist_ok=True)
        canonical = _abs_url(f"/article/{slug}/")
        img = story.get("image_url") or ""
        if img.startswith("http"):
            story["image_url_abs"] = img
        elif img:
            if not img.startswith(SETTINGS.news_base_path):
                img = _url_for(img)
            story["image_url"] = img
            story["image_url_abs"] = f"{SETTINGS.site_url.rstrip('/')}{img}"
        else:
            story["image_url_abs"] = ""
        story["published_label"] = format_story_date(story.get("published_at"))
        story["published_iso"] = to_iso8601(story.get("published_at"))
        meta_desc = (story.get("meta_description") or story.get("seo_title") or story.get("title") or "")[:300]
        story["meta_description_short"] = meta_desc
        (dest / "index.html").write_text(
            article_tpl.render(story=story, canonical=canonical, extra_head=""),
            encoding="utf-8",
        )

    index_stories = []
    for row in stories[:48]:
        s = dict(row)
        img = s.get("image_url") or ""
        if img.startswith("/") and SETTINGS.news_base_path not in img:
            s["image_url"] = _url_for(img if img.startswith("/media") else f"/media/{s.get('slug','')}/01.jpg")
        s["published_label"] = format_story_date(s.get("published_at"))
        index_stories.append(s)

    (news_out / "index.html").write_text(
        index_tpl.render(
            stories=index_stories,
            total=len(stories),
            site_tagline=SETTINGS.site_tagline,
        ),
        encoding="utf-8",
    )

    (news_out / "feed.xml").write_text(
        feed_tpl.render(stories=[dict(s) for s in stories[:50]]),
        encoding="utf-8",
    )

    sitemap_urls = [
        f"  <url><loc>{_abs_url('/')}</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>"
    ]
    for slug, published_at in slugs:
        lastmod = (published_at or "")[:10]
        loc = _abs_url(f"/article/{slug}/")
        sitemap_urls.append(
            f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(sitemap_urls)
        + "\n</urlset>\n"
    )
    (news_out / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    (news_out / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {_abs_url('/sitemap.xml')}\n",
        encoding="utf-8",
    )

    static_src = project_root() / "static"
    if static_src.exists():
        _copy_tree(static_src, news_out / "static")

    media_src = project_root() / "data" / "media"
    media_dest = news_out / "media"
    media_dest.mkdir(parents=True, exist_ok=True)
    for child in media_dest.iterdir():
        if child.is_dir() and child.name not in live_slugs:
            shutil.rmtree(child, ignore_errors=True)
    if media_src.exists():
        for slug_dir in media_src.iterdir():
            if not slug_dir.is_dir() or slug_dir.name not in live_slugs:
                continue
            target = media_dest / slug_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(slug_dir, target)

    repo_root = export_root()
    ensure_indexnow_key_file(repo_root, SETTINGS.indexnow_key)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (news_out / "publish-meta.json").write_text(
        json.dumps(
            {
                "generated_at": generated,
                "article_count": len(stories),
                "site_url": SETTINGS.site_url,
                "news_path": SETTINGS.news_base_path,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "export_dir": str(news_out),
        "articles": len(stories),
        "generated_at": generated,
        "news_url": _abs_url("/"),
    }