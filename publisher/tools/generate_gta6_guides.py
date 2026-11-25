#!/usr/bin/env python3
"""Generate Voice-themed GTA 6 walkthrough hub + mission pages for detailz.xyz (original copy only)."""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SITE_URL = "https://detailz.xyz"
SITE_NAME = "Detailz"
HUB_PATH = "/gta-6-full-walkthrough-all-missions/"
PUBLISHED = "2026-11-25T12:00:00+00:00"

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STAT_ROOT = Path.home() / "Documents" / "GitHub" / "stat"
STAT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STAT_ROOT
MISSIONS_JSON = SCRIPT_DIR / "gta6_missions.json"


def slugify(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-").replace("…", "")
    text = re.sub(r"\*[^*]+\*", " ", text)
    text = re.sub(r"\[([^\]]+)\]", r"\1 ", text)
    base = text.split("(")[0].strip() if "(" in text else text.strip()
    base = re.sub(r"[^\w\s\-]", "", base, flags=re.UNICODE)
    base = re.sub(r"[\s_]+", "-", base.lower()).strip("-")
    base = re.sub(r"-+", "-", base)
    return base or "mission"


def mission_key(chapter_id: str, mission: str) -> str:
    return f"{chapter_id}-{slugify(mission)}"


def snf_mission_key(snf_id: str, questline_id: str, label: str) -> str:
    return f"{snf_id}-{questline_id}-{slugify(label)}"


def chapter_mission_lookup(data: dict) -> dict[tuple[str, str], str]:
    """(chapter_id, mission_title) -> url path slug key under /gta6/."""
    out: dict[tuple[str, str], str] = {}
    for ch in data.get("chapters", []):
        for mission in ch["missions"]:
            out[(ch["id"], mission)] = mission_key(ch["id"], mission)
    return out


def collect_page_keys(data: dict) -> set[str]:
    keys: set[str] = set()
    for ch in data.get("chapters", []):
        for mission in ch["missions"]:
            keys.add(mission_key(ch["id"], mission))
    for snf_ch in data.get("strangers_and_freaks", []):
        for ql in snf_ch.get("questlines", []):
            for entry in ql.get("missions", []):
                if entry.get("same_as_chapter") and entry.get("same_as_mission"):
                    continue
                keys.add(snf_mission_key(snf_ch["id"], ql["id"], entry["label"]))
    return keys


def cleanup_orphaned_mission_dirs(gta6_dir: Path, valid_keys: set[str]) -> list[str]:
    """Remove /gta6/<slug>/ folders not in the current mission index (keeps static/ and sitemap.xml)."""
    removed: list[str] = []
    if not gta6_dir.is_dir():
        return removed
    for child in gta6_dir.iterdir():
        if child.name == "static":
            continue
        if child.is_file():
            continue
        if child.name not in valid_keys:
            shutil.rmtree(child)
            removed.append(child.name)
    return removed


def ad_unit(wrapper: str = "vce-ad vce-ad-container") -> str:
    return f"""<div class="{wrapper}">
<ins class="adsbygoogle" style="display:block; text-align:center;" data-ad-layout="in-article" data-ad-format="fluid" data-ad-client="ca-pub-8599957311549533" data-ad-slot="9219056455"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""


def page_shell(
    *,
    title: str,
    meta_description: str,
    canonical: str,
    breadcrumb_html: str,
    body_class: str,
    extra_head: str,
    main_html: str,
    nav_current: str,
) -> str:
    nav_news = 'current-menu-item' if nav_current == "news" else ""
    nav_gta = 'class="current-menu-item"' if nav_current == "gta" else ""
    gta_li = f'<li {nav_gta}><a href="/gta-6-full-walkthrough-all-missions/"' + (
        ' aria-current="page"' if nav_current == "gta" else ""
    ) + ">GTA 6 Guide</a></li>"

    return f"""<!DOCTYPE html>
<html lang="en-US" class="no-js no-svg">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="user-scalable=yes, width=device-width, initial-scale=1.0, maximum-scale=1, minimum-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(meta_description, quote=True)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="keywords" content="GTA 6, GTA VI, Grand Theft Auto 6, walkthrough, mission guide, story missions, Vice City, Lucia, Jason">
<link rel="canonical" href="{html.escape(canonical)}">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME} News" href="{SITE_URL}/news/feed.xml">
<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Open+Sans%3A400%7CRoboto+Slab%3A400%2C300&amp;display=swap">
<link rel="stylesheet" href="/wp-content/themes/voice/assets/css/min.css?ver=2.9.9">
<link rel="stylesheet" href="/news/static/news.css">
<link rel="stylesheet" href="/gta6/static/gta6.css">
{extra_head}
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8599957311549533"
     crossorigin="anonymous"></script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-FYM5BSJPNZ"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-FYM5BSJPNZ');
</script>
</head>
<body class="wp-embed-responsive wp-theme-voice vce-sid-right voice-v_2_9_9 {body_class}">
<div id="vce-main">
<header id="header" class="main-header">
<div class="container header-main-area header-3-wrapper">
  <div class="site-branding">
    <span class="site-title"><a href="/" rel="home" class="has-logo">
      <img src="/wp-content/uploads/2022/06/newlogo-1.png" alt="Detailz" class="vce-logo">
    </a></span>
  </div>
  <nav id="site-navigation" class="main-navigation" role="navigation">
    <ul class="nav-menu">
      <li><a href="/">Home</a></li>
      <li><a href="/category/entertainment/">Entertainment</a></li>
      <li><a href="/category/celebs/">Celebs</a></li>
      <li class="{nav_news}"><a href="/news/">News</a></li>
      {gta_li}
    </ul>
  </nav>
</div>
</header>
<div id="main-wrapper">
{ad_unit("vce-ad-below-header vce-ad-container")}
<div id="mks-breadcrumbs" class="container mks-bredcrumbs-container">
  <p id="breadcrumbs">{breadcrumb_html}</p>
</div>
<div id="content" class="container site-content vce-sid-right">
  <div id="primary" class="vce-main-content">
    <main id="main" class="main-box main-box-single">
{main_html}
    </main>
  </div>
</div>
{ad_unit("vce-ad-above-footer vce-ad-container")}
<footer id="footer" class="site-footer">
  <div class="container">
    <div class="site-info">GTA 6 mission names and structure follow the public Grand Theft Auto VI story order. Detailz guides are independent write-ups for players — not affiliated with Rockstar Games.</div>
  </div>
</footer>
</div>
</body>
</html>
"""


def collection_ld(title: str, description: str, canonical: str, items: list[dict]) -> str:
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": description,
        "url": canonical,
        "datePublished": PUBLISHED,
        "dateModified": PUBLISHED,
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": f"{SITE_URL}/"},
        "about": {
            "@type": "VideoGame",
            "name": "Grand Theft Auto VI",
            "gamePlatform": ["PlayStation 5", "Xbox Series X|S", "PC"],
        },
        "hasPart": [
            {"@type": "WebPage", "name": it["name"], "url": it["url"]} for it in items[:50]
        ],
    }
    return f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'


def article_ld(title: str, description: str, canonical: str, mission_name: str) -> str:
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "url": canonical,
        "datePublished": PUBLISHED,
        "dateModified": PUBLISHED,
        "author": {"@type": "Organization", "name": SITE_NAME, "url": f"{SITE_URL}/"},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/wp-content/uploads/2022/06/newlogo-1.png"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "about": {"@type": "VideoGame", "name": "Grand Theft Auto VI"},
        "keywords": f"GTA 6, {mission_name}, walkthrough, mission guide",
    }
    return f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'


def og_tags(title: str, description: str, canonical: str, og_type: str) -> str:
    return f"""<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{html.escape(title, quote=True)}">
<meta property="og:description" content="{html.escape(description, quote=True)}">
<meta property="og:url" content="{html.escape(canonical)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html.escape(title, quote=True)}">
<meta name="twitter:description" content="{html.escape(description, quote=True)}">"""


def mission_body(
    mission: str,
    chapter_title: str,
    prev_url: str | None,
    next_url: str | None,
    *,
    kind: str = "story",
) -> str:
    kind_note = (
        "This Strangers &amp; Freaks side quest is part of GTA 6&apos;s optional questlines — trophy hunters and 100% completion players often need it."
        if kind == "snf"
        else "This page tracks story progression for the GTA 6 (GTA VI) main campaign."
    )
    prev_next = '<nav class="gta6-mission-nav" aria-label="Mission navigation"><ul>'
    if prev_url:
        prev_next += f'<li class="prev"><a href="{prev_url}">&larr; Previous mission</a></li>'
    if next_url:
        prev_next += f'<li class="next"><a href="{next_url}">Next mission &rarr;</a></li>'
    prev_next += "</ul></nav>"

    return f"""      <article class="vce-single post type-post status-publish hentry category-gaming gta6-mission">
        <header class="entry-header">
          <h1 class="entry-title">{html.escape(mission)} — GTA 6 Walkthrough</h1>
          <p class="gta6-chapter-label">{html.escape(chapter_title)}</p>
        </header>
{ad_unit()}
        <div class="entry-headline"><p>Step-by-step Grand Theft Auto VI story help for <strong>{html.escape(mission)}</strong> in {html.escape(chapter_title)}: what to do, optional objectives to watch for, and links to the full mission list.</p></div>
{ad_unit()}
        <div class="entry-content">
          <h2>Mission overview</h2>
          <p>{kind_note} This guide covers <strong>{html.escape(mission)}</strong> in {html.escape(chapter_title)}. Use our <a href="/gta-6-full-walkthrough-all-missions/">complete GTA 6 walkthrough — all missions</a> index so you never lose your place in Vice City and Leonida.</p>
          <h2>Before you start</h2>
          <ul>
            <li>Save your game at the nearest safe location when the mission becomes available.</li>
            <li>Check the map for any secondary objective markers tied to this storyline beat.</li>
            <li>Optional and missable tasks (when labeled in the mission name) should be completed during the same chapter when possible.</li>
          </ul>
{ad_unit()}
          <h2>Walkthrough notes</h2>
          <p>We are expanding this guide with detailed routes, combat tips, and collectibles for <em>{html.escape(mission)}</em>. Bookmark this URL and check back after major GTA 6 updates or post-launch patches.</p>
          <p>Players searching for &ldquo;GTA 6 {html.escape(mission)} walkthrough,&rdquo; &ldquo;Grand Theft Auto VI mission guide,&rdquo; or &ldquo;GTA VI story help&rdquo; can use this page as the canonical Detailz reference for this mission name and chapter.</p>
          {prev_next}
          <p><a href="/gta-6-full-walkthrough-all-missions/">Back to all GTA 6 missions</a></p>
        </div>
{ad_unit()}
      </article>"""


def hub_body(chapters_html: str, snf_html: str, mission_count: int, snf_count: int) -> str:
    return f"""      <article class="vce-single post type-post status-publish hentry category-gaming gta6-hub">
        <header class="entry-header">
          <h1 class="entry-title">GTA 6 Full Walkthrough — All Missions</h1>
        </header>
{ad_unit()}
        <div class="entry-headline"><p>Every <strong>main story</strong> mission and <strong>Strangers &amp; Freaks</strong> side quest in <strong>Grand Theft Auto VI (GTA 6 / GTA VI)</strong> — {mission_count} story missions plus {snf_count} dedicated side-quest pages, all under <code>/gta6/</code> on Detailz.</p></div>
{ad_unit()}
        <div class="entry-content gta6-hub-content">
          <h2>How to use this GTA 6 guide</h2>
          <p>Pick a chapter below for the campaign in order (Prologue through Chapter 5), including optional and missable jobs. Scroll to <a href="#strangers-and-freaks">Strangers &amp; Freaks</a> for side questlines. Built for searches like &ldquo;GTA 6 full walkthrough,&rdquo; &ldquo;GTA VI all missions,&rdquo; &ldquo;Strangers and Freaks GTA 6,&rdquo; and &ldquo;Grand Theft Auto 6 optional missions.&rdquo;</p>
{ad_unit()}
          <h2 id="main-story">Main story missions</h2>
          {chapters_html}
          <h2 id="strangers-and-freaks">Strangers &amp; Freaks</h2>
          <p>Side missions and questlines — many count toward 100% completion or trophies. Some tie to the main story under a different name; those links point to the same mission guide as the story list.</p>
{ad_unit()}
          {snf_html}
          <h2>About these guides</h2>
          <p>Detailz publishes original gaming guides in the same Voice layout as our news section, with clear titles and metadata so Google and players can find each mission. We do not republish third-party walkthrough text; each page is our own index and expandable guide for Rockstar&apos;s GTA 6 campaign.</p>
        </div>
{ad_unit()}
      </article>"""


def main() -> None:
    data = json.loads(MISSIONS_JSON.read_text(encoding="utf-8"))
    hub_dir = STAT_ROOT / "gta-6-full-walkthrough-all-missions"
    gta6_dir = STAT_ROOT / "gta6"
    static_dir = gta6_dir / "static"
    hub_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    (static_dir / "gta6.css").write_text(
        """/* GTA 6 guide hub — Voice-friendly lists */
.gta6-hub-content h2 { margin-top: 2rem; }
.gta6-chapter { margin: 1.5rem 0 2rem; }
.gta6-chapter h3 { font-size: 2.2rem; margin-bottom: 0.75rem; }
.gta6-chapter h4 { font-size: 1.8rem; margin: 1rem 0 0.5rem; color: #333; }
.gta6-mission-list { list-style: none; padding: 0; margin: 0; }
.gta6-mission-list li { margin: 0.35rem 0; font-size: 1.5rem; }
.gta6-mission-list a { text-decoration: none; border-bottom: 1px solid #cf4d35; }
.gta6-chapter-label { color: #888; font-size: 1.4rem; margin-top: 0.5rem; }
.gta6-mission-nav ul { display: flex; flex-wrap: wrap; gap: 1rem; justify-content: space-between; list-style: none; padding: 1.5rem 0; margin: 0; border-top: 1px solid #eee; }
.gta6-questline { margin-bottom: 1.25rem; }
""",
        encoding="utf-8",
    )

    main_lookup = chapter_mission_lookup(data)
    flat: list[tuple[dict, str, str, str, str]] = []
    sitemap_urls: list[str] = []
    ld_items: list[dict] = []

    for ch in data["chapters"]:
        for mission in ch["missions"]:
            key = mission_key(ch["id"], mission)
            path = f"/gta6/{key}/"
            url = f"{SITE_URL}{path}"
            flat.append((ch, mission, key, url, "story"))
            sitemap_urls.append(url)
            ld_items.append({"name": mission, "url": url})

    snf_page_count = 0
    for snf_ch in data.get("strangers_and_freaks", []):
        for ql in snf_ch.get("questlines", []):
            for entry in ql.get("missions", []):
                label = entry["label"]
                same = entry.get("same_as_chapter") and entry.get("same_as_mission")
                if same:
                    continue
                key = snf_mission_key(snf_ch["id"], ql["id"], label)
                pseudo = {"id": snf_ch["id"], "title": snf_ch["title"]}
                path = f"/gta6/{key}/"
                url = f"{SITE_URL}{path}"
                flat.append((pseudo, label, key, url, "snf"))
                sitemap_urls.append(url)
                ld_items.append({"name": label, "url": url})
                snf_page_count += 1

    def href_for_snf_entry(snf_ch: dict, ql: dict, entry: dict) -> str:
        if entry.get("same_as_chapter") and entry.get("same_as_mission"):
            ref = main_lookup.get((entry["same_as_chapter"], entry["same_as_mission"]))
            if ref:
                return f"/gta6/{ref}/"
        key = snf_mission_key(snf_ch["id"], ql["id"], entry["label"])
        return f"/gta6/{key}/"

    # Hub
    chapters_parts = []
    for ch in data["chapters"]:
        lis = []
        for mission in ch["missions"]:
            key = mission_key(ch["id"], mission)
            lis.append(f'<li><a href="/gta6/{key}/">{html.escape(mission)}</a></li>')
        chapters_parts.append(
            f'<section class="gta6-chapter" id="{html.escape(ch["id"])}">'
            f"<h3>{html.escape(ch['title'])}</h3>"
            f'<ul class="gta6-mission-list">{"".join(lis)}</ul></section>'
        )
        chapters_parts.append(ad_unit())

    snf_parts = []
    for snf_ch in data.get("strangers_and_freaks", []):
        snf_parts.append(
            f'<section class="gta6-chapter" id="{html.escape(snf_ch["id"])}">'
            f"<h3>{html.escape(snf_ch['title'])}</h3>"
        )
        for ql in snf_ch.get("questlines", []):
            if not ql.get("missions"):
                continue
            snf_parts.append(f'<div class="gta6-questline"><h4>{html.escape(ql["title"])}</h4><ul class="gta6-mission-list">')
            for entry in ql["missions"]:
                href = href_for_snf_entry(snf_ch, ql, entry)
                snf_parts.append(f'<li><a href="{href}">{html.escape(entry["label"])}</a></li>')
            snf_parts.append("</ul></div>")
        snf_parts.append("</section>")
        snf_parts.append(ad_unit())

    main_count = sum(len(c["missions"]) for c in data["chapters"])
    hub_title = "GTA 6 Full Walkthrough — All Missions (Grand Theft Auto VI Guide) | Detailz"
    hub_desc = (
        f"Complete GTA 6 (GTA VI) walkthrough: {main_count} main story missions (Prologue–Chapter 5), "
        f"optional jobs, Cartel Heist and VCIA Takedown steps, plus {snf_page_count} Strangers & Freaks guides on Detailz."
    )
    hub_canonical = f"{SITE_URL}{HUB_PATH}"
    hub_extra = og_tags(hub_title, hub_desc, hub_canonical, "website") + "\n" + collection_ld(
        "GTA 6 Full Walkthrough — All Missions", hub_desc, hub_canonical, ld_items
    )
    hub_breadcrumb = (
        '<span><span><a href="/">Home</a></span> » '
        '<span class="breadcrumb_last">GTA 6 Full Walkthrough — All Missions</span></span>'
    )
    hub_html = page_shell(
        title=hub_title,
        meta_description=hub_desc,
        canonical=hub_canonical,
        breadcrumb_html=hub_breadcrumb,
        body_class="wp-singular single single-post vce-single gta6-hub-page",
        extra_head=hub_extra,
        main_html=hub_body("".join(chapters_parts), "".join(snf_parts), main_count, snf_page_count),
        nav_current="gta",
    )
    (hub_dir / "index.html").write_text(hub_html, encoding="utf-8")
    sitemap_urls.insert(0, hub_canonical)

    for i, (ch, mission, key, url, kind) in enumerate(flat):
        prev_url = f"/gta6/{flat[i - 1][2]}/" if i > 0 else None
        next_url = f"/gta6/{flat[i + 1][2]}/" if i + 1 < len(flat) else None
        label = "Strangers & Freaks" if kind == "snf" else "Walkthrough"
        page_title = f"{mission} — GTA 6 {label} ({ch['title']}) | Detailz"
        meta_desc = (
            f"GTA 6 / GTA VI guide for {mission} — {ch['title']}. "
            + (
                "Strangers & Freaks side quest help, trophy tips, and links to the full GTA 6 mission list on Detailz."
                if kind == "snf"
                else "Grand Theft Auto 6 story mission guide, optional objectives, and chapter index on Detailz."
            )
        )
        breadcrumb = (
            '<span><span><a href="/">Home</a></span> » '
            f'<span><a href="/gta-6-full-walkthrough-all-missions/">GTA 6 Walkthrough</a></span> » '
            f'<span><a href="/gta-6-full-walkthrough-all-missions/#{html.escape(ch["id"])}">{html.escape(ch["title"])}</a></span> » '
            f'<span class="breadcrumb_last">{html.escape(mission)}</span></span>'
        )
        extra = og_tags(page_title, meta_desc, url, "article") + "\n" + article_ld(page_title, meta_desc, url, mission)
        out = page_shell(
            title=page_title,
            meta_description=meta_desc,
            canonical=url,
            breadcrumb_html=breadcrumb,
            body_class="wp-singular single single-post vce-single gta6-mission-page",
            extra_head=extra,
            main_html=mission_body(mission, ch["title"], prev_url, next_url, kind=kind),
            nav_current="gta",
        )
        mdir = gta6_dir / key
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / "index.html").write_text(out, encoding="utf-8")

    # Sitemap
    lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sm_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in sitemap_urls:
        sm_lines.append("  <url>")
        sm_lines.append(f"    <loc>{u}</loc>")
        sm_lines.append(f"    <lastmod>{lastmod}</lastmod>")
        sm_lines.append("    <changefreq>weekly</changefreq>")
        priority = "1.0" if u == hub_canonical else "0.8"
        sm_lines.append(f"    <priority>{priority}</priority>")
        sm_lines.append("  </url>")
    sm_lines.append("</urlset>")
    (gta6_dir / "sitemap.xml").write_text("\n".join(sm_lines) + "\n", encoding="utf-8")

    for sitemap_name in ("sitemap.xml", "sitemap_index.xml"):
        sp = STAT_ROOT / sitemap_name
        if not sp.exists():
            continue
        text = sp.read_text(encoding="utf-8")
        entry = "\t<sitemap>\n\t\t<loc>https://detailz.xyz/gta6/sitemap.xml</loc>\n\t\t<lastmod>" + lastmod + "</lastmod>\n\t</sitemap>"
        if "gta6/sitemap.xml" not in text:
            text = text.replace("</sitemapindex>", entry + "\n</sitemapindex>")
            sp.write_text(text, encoding="utf-8")

    removed = cleanup_orphaned_mission_dirs(gta6_dir, collect_page_keys(data))
    if removed:
        print(f"Removed {len(removed)} orphaned mission folder(s): {', '.join(sorted(removed)[:8])}" + (
            f" ... (+{len(removed) - 8} more)" if len(removed) > 8 else ""
        ))

    print(f"Wrote hub + {len(flat)} pages ({main_count} story + {snf_page_count} SNF-only) under {STAT_ROOT}")
    print(f"Hub: {hub_canonical}")


if __name__ == "__main__":
    main()