"""
Detailz trending publisher: Google Trends RSS -> articles -> /trending/ static export -> GitHub.
"""

from __future__ import annotations

import argparse
import logging
import sys
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

from app.trending_export import export_trending_site  # noqa: E402
from app.trending_git_publish import publish_trending_to_github  # noqa: E402
from app.trending_sync import sync_trending  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("trending_publisher")


def run_once(*, deploy: str) -> None:
    log.info("Fetching Google Trends...")
    sync_result = sync_trending()
    log.info("Sync: %s", sync_result)

    if not sync_result.get("new_articles"):
        log.info("No new trending keywords; still exporting sitemap/index for freshness")
    else:
        log.info("Created %s new trending articles", sync_result["new_articles"])

    log.info("Exporting /trending/...")
    export_result = export_trending_site()
    log.info("Export: %s", export_result)

    if deploy == "github":
        pub = publish_trending_to_github(new_slugs=sync_result.get("new_slugs") or [])
        if pub.get("pushed"):
            log.info("Pushed: %s", pub.get("commit_message"))
            log.info("Sitemap ping: %s", pub.get("sitemap_ping"))
        else:
            log.info("No git push: %s", pub.get("reason"))
    elif deploy != "none":
        raise ValueError(f"Unknown deploy: {deploy}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detailz trending publisher")
    parser.add_argument("--deploy", default="github", choices=("github", "none"))
    args = parser.parse_args()
    run_once(deploy=args.deploy)


if __name__ == "__main__":
    main()