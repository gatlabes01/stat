from __future__ import annotations

from pathlib import Path

import httpx

from app.config import SETTINGS
from app.paths import project_root
from app.webp_image import save_as_webp

MEDIA_ROOT = project_root() / "data" / "media"
_LEGACY_EXTS = (".jpg", ".jpeg", ".png")


def _ensure_webp(dest_dir: Path, idx: int, data: bytes | None = None) -> Path | None:
    filename = f"{idx:02d}.webp"
    path = dest_dir / filename
    if path.is_file() and path.stat().st_size > 0:
        return path
    for ext in _LEGACY_EXTS:
        cand = dest_dir / f"{idx:02d}{ext}"
        if cand.is_file() and cand.stat().st_size > 0:
            if save_as_webp(cand.read_bytes(), path):
                return path
    if data and save_as_webp(data, path):
        return path
    return None


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
            path = _ensure_webp(dest_dir, idx)
            if path is None:
                try:
                    resp = client.get(remote)
                    resp.raise_for_status()
                    path = _ensure_webp(dest_dir, idx, resp.content)
                except httpx.HTTPError:
                    path = None
            if path is None:
                cached.append({**img, "local_url": remote, "cached": False})
                continue
            media_root = SETTINGS.news_base_path.rstrip("/")
            filename = path.name
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
