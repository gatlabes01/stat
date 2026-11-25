from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.config import SETTINGS
from app.static_export import news_root_dir


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def publish_to_github(export_dir: Path | None = None, message: str | None = None) -> dict:
    root = Path(SETTINGS.repo_root).resolve()
    news_dir = news_root_dir(export_dir).resolve()
    if not (root / ".git").exists():
        raise RuntimeError(f"No git repo at {root}. Run git init and add a GitHub remote first.")

    try:
        rel_site = news_dir.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"News export {news_dir} is not under repo root {root}") from exc
    commit_msg = message or f"Publish news {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"

    add = _run(["git", "add", str(rel_site)], root)
    if add.returncode != 0:
        raise RuntimeError(add.stderr or add.stdout)

    status = _run(["git", "status", "--porcelain", str(rel_site)], root)
    if not status.stdout.strip():
        return {"pushed": False, "reason": "no_changes", "branch": SETTINGS.git_branch}

    commit = _run(["git", "commit", "-m", commit_msg], root)
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr or commit.stdout)

    push = _run(
        ["git", "push", SETTINGS.git_remote, SETTINGS.git_branch],
        root,
    )
    if push.returncode != 0:
        raise RuntimeError(push.stderr or push.stdout)

    return {
        "pushed": True,
        "branch": SETTINGS.git_branch,
        "remote": SETTINGS.git_remote,
        "commit_message": commit_msg,
    }