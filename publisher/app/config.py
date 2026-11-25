from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    site_name: str
    site_url: str
    site_base_path: str
    news_base_path: str
    trending_base_path: str
    trending_rss_url: str
    trending_geo: str
    trending_max_per_run: int
    trending_min_traffic_score: int
    trending_max_per_keyword: int
    indexnow_key: str | None
    site_tagline: str
    tmz_rss_url: str
    sync_interval_seconds: int
    enrich_batch_size: int
    openai_api_key: str | None
    openai_base_url: str
    openai_model: str
    push_interval_hours: float
    git_remote: str
    git_branch: str
    repo_root: str
    google_site_verification: str | None
    deploy_target: str
    cloudflare_pages_project: str
    cloudflare_account_id: str | None


def load_settings() -> Settings:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return Settings(
        site_name=os.environ.get("SITE_NAME", "Detailz"),
        site_url=os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/"),
        site_base_path=os.environ.get("SITE_BASE_PATH", "").rstrip("/"),
        news_base_path=os.environ.get("NEWS_BASE_PATH", "/news").rstrip("/"),
        trending_base_path=os.environ.get("TRENDING_BASE_PATH", "/trending").rstrip("/"),
        trending_rss_url=os.environ.get(
            "TRENDING_RSS_URL",
            "https://trends.google.com/trending/rss?geo=US",
        ),
        trending_geo=os.environ.get("TRENDING_GEO", "US"),
        trending_max_per_run=int(os.environ.get("TRENDING_MAX_PER_RUN", "15")),
        trending_min_traffic_score=int(os.environ.get("TRENDING_MIN_TRAFFIC_SCORE", "0")),
        trending_max_per_keyword=int(os.environ.get("TRENDING_MAX_PER_KEYWORD", "3")),
        indexnow_key=os.environ.get("INDEXNOW_KEY") or None,
        site_tagline=os.environ.get(
            "SITE_TAGLINE",
            "Celebrity news and entertainment, rewritten for readers who want the full picture.",
        ),
        tmz_rss_url=os.environ.get("TMZ_RSS_URL", "https://www.tmz.com/rss.xml"),
        sync_interval_seconds=int(os.environ.get("SYNC_INTERVAL_SECONDS", "180")),
        enrich_batch_size=int(os.environ.get("ENRICH_BATCH_SIZE", "8")),
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        openai_base_url=base,
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        push_interval_hours=float(os.environ.get("PUSH_INTERVAL_HOURS", "2")),
        git_remote=os.environ.get("GIT_REMOTE", "origin"),
        git_branch=os.environ.get("GIT_BRANCH", "main"),
        repo_root=os.environ.get("REPO_ROOT", os.getcwd()),
        google_site_verification=os.environ.get("GOOGLE_SITE_VERIFICATION") or None,
        deploy_target=os.environ.get("DEPLOY_TARGET", "github").lower(),
        cloudflare_pages_project=os.environ.get("CLOUDFLARE_PAGES_PROJECT", "detailz"),
        cloudflare_account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID") or None,
    )


SETTINGS = load_settings()