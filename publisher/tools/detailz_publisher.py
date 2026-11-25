"""
Detailz publisher: sync TMZ -> enrich -> export static SEO site -> deploy.

Deploy targets: Cloudflare Pages (default) or optional GitHub commit.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _app_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.cloudflare_deploy import deploy_to_cloudflare  # noqa: E402
from app.config import SETTINGS  # noqa: E402
from app.git_publish import publish_to_github  # noqa: E402
from app.static_export import export_static_site  # noqa: E402
from app.sync import sync_tmz  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("detailz_publisher")


def _deploy(target: str) -> None:
    if target == "none":
        log.info("Skipping deploy")
        return
    if target == "cloudflare":
        log.info("Deploying to Cloudflare Pages (%s)...", SETTINGS.cloudflare_pages_project)
        result = deploy_to_cloudflare()
        log.info("Cloudflare deploy OK: %s", result.get("project"))
        return
    if target == "github":
        log.info("Pushing site/ to GitHub...")
        pub = publish_to_github()
        if pub.get("pushed"):
            log.info("Pushed to %s/%s", pub["remote"], pub["branch"])
        else:
            log.info("Nothing to push (%s)", pub.get("reason"))
        return
    raise ValueError(f"Unknown deploy target: {target}")


def run_once(*, deploy: str) -> None:
    log.info("Syncing TMZ feed...")
    sync_result = sync_tmz()
    log.info(
        "Sync done: fetched=%s enriched=%s total_published=%s",
        sync_result.get("fetched"),
        sync_result.get("enriched_this_run"),
        sync_result.get("published"),
    )

    log.info("Exporting static SEO site...")
    export_result = export_static_site()
    log.info(
        "Export done: %s articles -> %s",
        export_result["articles"],
        export_result["export_dir"],
    )

    _deploy(deploy)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detailz publisher")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Skip TMZ sync",
    )
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="Export only, no Cloudflare/GitHub",
    )
    parser.add_argument(
        "--deploy",
        choices=("cloudflare", "github", "none"),
        default=None,
        help="Override DEPLOY_TARGET from .env",
    )
    args = parser.parse_args()

    deploy = args.deploy or SETTINGS.deploy_target
    if deploy not in ("cloudflare", "github", "none"):
        deploy = "cloudflare"
    if args.no_deploy:
        deploy = "none"

    interval = SETTINGS.push_interval_hours * 3600

    def cycle() -> None:
        if args.export_only:
            export_static_site()
            _deploy(deploy)
        else:
            run_once(deploy=deploy)

    if args.loop:
        log.info(
            "Loop: every %s h | deploy=%s | SITE_URL=%s",
            SETTINGS.push_interval_hours,
            deploy,
            SETTINGS.site_url,
        )
        while True:
            try:
                cycle()
            except Exception:
                log.exception("Publisher cycle failed")
            log.info("Sleeping %s s...", interval)
            time.sleep(interval)
    else:
        cycle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())