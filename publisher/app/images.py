from __future__ import annotations

import re
from pathlib import Path

import httpx

from app.config import SETTINGS

from app.paths import project_root

MEDIA_ROOT = project_root() / "data" / "media"


def _extension(url: str) -> str:
    m = re.search(r"\.(jpg|jpeg|png|webp)(?:\?|$)", url, re.I)
    return f".{m.group(1).lower()}" if m else ".jpg"


def cache_story_images(slug: str, images: list[dict]) -> list[dict]:
    if not images:
        return []

    dest_dir = MEDIA_ROOT / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    cached: list[dict] = []

    with httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DetailzBot/1.0)"},
        follow_redirects=True,
    ) as client:
        for idx, img in enumerate(images, start=1):
            remote = img["url"]
            filename = f"{idx:02d}.webp"
            path = dest_dir / filename
            if not path.exists():
                from app.webp_image import save_as_webp

                existing = None
                for ext in (".jpg", ".jpeg", ".png"):
                    cand = dest_dir / f"{idx:02d}{ext}"
                    if cand.is_file():
                        existing = cand
                        break
                converted = False
                if existing:
                    converted = save_as_webp(existing.read_bytes(), path)
                if not converted:
                    try:
                        resp = client.get(remote)
                        resp.raise_for_status()
                        if not save_as_webp(resp.content, path):
                            fallback = dest_dir / f"{idx:02d}{_extension(remote)}"
                            fallback.write_bytes(resp.content)
                            path = fallback
                            filename = fallback.name
                    except httpx.HTTPError:
                        cached.append({**img, "local_url": remote, "cached": False})
                        continue
            media_root = SETTINGS.news_base_path.rstrip("/")
            local_url = f"{media_root}/media/{slug}/{filename}"
            cached.append(
                {
                    **img,
                    "local_url": local_url,
                    "cached": True,
                    "file": str(path),
                }
            )
    return cached