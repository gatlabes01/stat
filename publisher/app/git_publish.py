from __future__ import annotations



import subprocess

from datetime import datetime, timezone

from pathlib import Path



from app.config import SETTINGS

from app.seo_ping import ensure_indexnow_key_file, ping_sitemap, submit_indexnow

from app.static_export import _abs_url, news_root_dir





def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:

    return subprocess.run(

        cmd,

        cwd=str(cwd),

        capture_output=True,

        text=True,

        check=False,

    )





def publish_to_github(

    export_dir: Path | None = None,

    message: str | None = None,

    new_slugs: list[str] | None = None,

) -> dict:

    root = Path(SETTINGS.repo_root).resolve()

    news_dir = news_root_dir(export_dir).resolve()

    if not (root / ".git").exists():

        raise RuntimeError(f"No git repo at {root}. Run git init and add a GitHub remote first.")



    try:

        rel_site = news_dir.relative_to(root)

    except ValueError as exc:

        raise RuntimeError(f"News export {news_dir} is not under repo root {root}") from exc



    rel_paths = [str(rel_site)]

    for name in ("sitemap_index.xml", "sitemap.xml"):

        p = root / name

        if p.exists():

            rel_paths.append(name)

    key_file = ensure_indexnow_key_file(root, SETTINGS.indexnow_key)

    if key_file and key_file.exists():

        rel_paths.append(key_file.name)



    commit_msg = message or f"Publish news {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"



    for rel in rel_paths:

        add = _run(["git", "add", rel], root)

        if add.returncode != 0:

            raise RuntimeError(add.stderr or add.stdout)



    status = _run(["git", "status", "--porcelain"] + rel_paths, root)

    if not status.stdout.strip():

        return {"pushed": False, "reason": "no_changes", "branch": SETTINGS.git_branch}



    commit = _run(["git", "commit", "-m", commit_msg], root)

    if commit.returncode != 0:

        raise RuntimeError(commit.stderr or commit.stdout)



    pull = _run(
        ["git", "pull", "--rebase", SETTINGS.git_remote, SETTINGS.git_branch],
        root,
    )
    if pull.returncode != 0:
        raise RuntimeError(pull.stderr or pull.stdout or "git pull --rebase failed")

    push = _run(

        ["git", "push", SETTINGS.git_remote, SETTINGS.git_branch],

        root,

    )

    if push.returncode != 0:

        raise RuntimeError(push.stderr or push.stdout)



    ping = ping_sitemap(_abs_url("/sitemap.xml"))

    indexnow: dict = {"skipped": True}

    if SETTINGS.indexnow_key and new_slugs:

        host = SETTINGS.site_url.rstrip("/")

        urls = [_abs_url(f"/article/{s}/") for s in new_slugs]

        indexnow = submit_indexnow(host, SETTINGS.indexnow_key, urls)



    return {

        "pushed": True,

        "branch": SETTINGS.git_branch,

        "remote": SETTINGS.git_remote,

        "commit_message": commit_msg,

        "sitemap_ping": ping,

        "indexnow": indexnow,

    }
