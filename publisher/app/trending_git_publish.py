from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import SETTINGS
from app.seo_ping import ensure_indexnow_key_file, ping_sitemap, submit_indexnow
from app.paths import project_root
from app.trending_export import _abs_url, trending_root_dir


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def publish_trending_to_github(
    export_dir: Path | None = None,
    message: str | None = None,
    new_slugs: list[str] | None = None,
) -> dict:
    root = Path(SETTINGS.repo_root).resolve()
    trend_dir = trending_root_dir(export_dir).resolve()
    if not (root / ".git").exists():
        raise RuntimeError(f"No git repo at {root}")

    rel_paths = [str(trend_dir.relative_to(root))]
    key_file = ensure_indexnow_key_file(root, SETTINGS.indexnow_key)
    if key_file and key_file.exists():
        rel_paths.append(key_file.name)

    db_path = project_root() / "data" / "trending.db"
    db_rel = str(db_path.relative_to(root)) if db_path.is_file() else None
    if db_rel:
        rel_paths.append(db_rel)

    commit_msg = message or f"Publish trending {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"

    for rel in rel_paths:
        add_cmd = ["git", "add", "-f", rel] if rel == db_rel else ["git", "add", rel]
        add = _run(add_cmd, root)
        if add.returncode != 0:
            raise RuntimeError(add.stderr or add.stdout)

    status = _run(["git", "status", "--porcelain"] + rel_paths, root)
    if not status.stdout.strip():
        return {"pushed": False, "reason": "no_changes", "branch": SETTINGS.git_branch}

    commit = _run(["git", "commit", "-m", commit_msg], root)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr or commit.stdout)

    last_err = ""
    for attempt in range(6):
        fetch = _run(["git", "fetch", SETTINGS.git_remote, SETTINGS.git_branch], root)
        if fetch.returncode != 0:
            last_err = fetch.stderr or fetch.stdout or "git fetch failed"
            time.sleep(2 * (attempt + 1))
            continue
        pull = _run(
            [
                "git",
                "pull",
                "--rebase",
                "--autostash",
                SETTINGS.git_remote,
                SETTINGS.git_branch,
            ],
            root,
        )
        if pull.returncode != 0:
            last_err = pull.stderr or pull.stdout or "git pull --rebase failed"
            _run(["git", "rebase", "--abort"], root)
            time.sleep(2 * (attempt + 1))
            continue
        push = _run(["git", "push", SETTINGS.git_remote, SETTINGS.git_branch], root)
        if push.returncode == 0:
            last_err = ""
            break
        last_err = push.stderr or push.stdout or "git push failed"
        time.sleep(2 * (attempt + 1))
    if last_err:
        raise RuntimeError(last_err)

    ping = ping_sitemap(_abs_url("/sitemap.xml"))
    ping.update(
        {f"hub_{k}": v for k, v in ping_sitemap(f"{SETTINGS.site_url.rstrip('/')}/sitemap_index.xml").items()}
    )
    indexnow = {"skipped": True}
    if SETTINGS.indexnow_key and new_slugs:
        host = SETTINGS.site_url.replace("https://", "").replace("http://", "").strip("/")
        urls = [_abs_url(f"/{s}/") for s in new_slugs]
        indexnow = submit_indexnow(host, SETTINGS.indexnow_key, urls)

    return {
        "pushed": True,
        "branch": SETTINGS.git_branch,
        "remote": SETTINGS.git_remote,
        "commit_message": commit_msg,
        "sitemap_ping": ping,
        "indexnow": indexnow,
    }
