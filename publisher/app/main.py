from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import database as db
from app.config import SETTINGS
from app.enrich import enrich_pending
from app.sync import COPYRIGHT_NOTICE, sync_tmz

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    try:
        sync_tmz()
    except Exception:
        pass

    async def poll_loop() -> None:
        while True:
            await asyncio.sleep(SETTINGS.sync_interval_seconds)
            try:
                sync_tmz()
            except Exception:
                pass

    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


MEDIA_DIR = ROOT / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=SETTINGS.site_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
templates = Jinja2Templates(directory=ROOT / "templates")
templates.env.globals["site_name"] = SETTINGS.site_name
templates.env.globals["site_url"] = SETTINGS.site_url


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
):
    conn = db.connect()
    offset = (page - 1) * per_page
    stories = db.list_published_stories(conn, limit=per_page, offset=offset)
    total = db.count_published_stories(conn)
    conn.close()
    pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stories": stories,
            "page": page,
            "pages": pages,
            "total": total,
            "site_tagline": SETTINGS.site_tagline,
            "copyright_notice": COPYRIGHT_NOTICE,
        },
    )


@app.get("/article/{slug}", response_class=HTMLResponse)
def article_page(request: Request, slug: str):
    conn = db.connect()
    story = db.get_story_by_slug(conn, slug)
    conn.close()
    if not story:
        raise HTTPException(status_code=404, detail="Article not found")
    canonical = f"{SETTINGS.site_url}/article/{story['slug']}"
    return templates.TemplateResponse(
        request,
        "article.html",
        {
            "story": story,
            "canonical": canonical,
            "copyright_notice": COPYRIGHT_NOTICE,
        },
    )


@app.get("/story/{story_id}", response_class=HTMLResponse)
def legacy_story_redirect(request: Request, story_id: int):
    conn = db.connect()
    story = db.get_story_by_id(conn, story_id)
    conn.close()
    if not story or not story["slug"]:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse(
        request,
        "article.html",
        {
            "story": story,
            "canonical": f"{SETTINGS.site_url}/article/{story['slug']}",
            "copyright_notice": COPYRIGHT_NOTICE,
        },
    )


@app.get("/sitemap.xml")
def sitemap():
    conn = db.connect()
    rows = db.all_published_slugs(conn)
    conn.close()
    urls = []
    for slug, published_at in rows:
        urls.append(
            f"  <url><loc>{SETTINGS.site_url}/article/{slug}</loc>"
            f"<lastmod>{(published_at or '')[:10]}</lastmod></url>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SETTINGS.site_url}/</loc></url>\n"
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=body, media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return f"User-agent: *\nAllow: /\nSitemap: {SETTINGS.site_url}/sitemap.xml\n"


@app.post("/api/sync")
def api_sync():
    return sync_tmz()


@app.post("/api/enrich")
def api_enrich():
    return enrich_pending()


@app.get("/api/stories")
def api_stories(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
):
    conn = db.connect()
    offset = (page - 1) * per_page
    rows = db.list_published_stories(conn, limit=per_page, offset=offset)
    total = db.count_published_stories(conn)
    conn.close()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows],
    }