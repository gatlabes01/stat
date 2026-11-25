from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.config import SETTINGS
from app.static_export import export_root


def _wrangler_cmd() -> str:
    path = shutil.which("wrangler")
    if path:
        return path
    raise RuntimeError(
        "Wrangler CLI not found. Install: npm install -g wrangler"
    )


def deploy_to_cloudflare(export_dir: Path | None = None) -> dict:
    site = export_dir or export_root()
    if not site.is_dir() or not (site / "index.html").is_file():
        raise RuntimeError(f"Missing static export at {site}")

    env = os.environ.copy()
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if token:
        env["CLOUDFLARE_API_TOKEN"] = token
    if SETTINGS.cloudflare_account_id:
        env["CLOUDFLARE_ACCOUNT_ID"] = SETTINGS.cloudflare_account_id

    cmd = [
        _wrangler_cmd(),
        "pages",
        "deploy",
        str(site),
        "--project-name",
        SETTINGS.cloudflare_pages_project,
        "--branch",
        "main",
        "--commit-dirty=true",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(site.parent))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "wrangler deploy failed")

    return {
        "deployed": True,
        "project": SETTINGS.cloudflare_pages_project,
        "output": (proc.stdout or "").strip()[-500:],
    }