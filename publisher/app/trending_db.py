from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import SETTINGS
from app.paths import project_root
from app.slug import slugify


def db_path() -> Path:
    return project_root() / "data" / "trending.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS trending_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            keyword_normalized TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            approx_traffic TEXT,
            traffic_score INTEGER DEFAULT 0,
            seo_title TEXT,
            meta_description TEXT,
            article_body TEXT,
            image_url TEXT,
            source_links TEXT,
            status TEXT NOT NULL DEFAULT 'published',
            published_at TEXT,
            created_at TEXT NOT NULL,
            trend_pub_date TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trending_published ON trending_topics(published_at DESC);
        """
    )
    conn.commit()
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trending_topics)")}
    for name, ddl in (
        ("h1", "ALTER TABLE trending_topics ADD COLUMN h1 TEXT"),
        ("faq_json", "ALTER TABLE trending_topics ADD COLUMN faq_json TEXT"),
        ("seo_keywords", "ALTER TABLE trending_topics ADD COLUMN seo_keywords TEXT"),
    ):
        if name not in cols:
            conn.execute(ddl)
    conn.commit()
    _migrate_allow_multi_per_keyword(conn)


def _table_sql(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='trending_topics'"
    ).fetchone()
    return row[0] if row else ""


def _migrate_allow_multi_per_keyword(conn: sqlite3.Connection) -> None:
    """Allow up to N articles per keyword (drop UNIQUE on keyword_normalized)."""
    sql = _table_sql(conn)
    if not sql or "keyword_normalized TEXT NOT NULL UNIQUE" not in sql.replace("\n", " "):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trending_norm ON trending_topics(keyword_normalized)"
        )
        conn.commit()
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trending_topics)")]
    col_list = ", ".join(cols)
    conn.executescript(
        f"""
        CREATE TABLE trending_topics_mig (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            keyword_normalized TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            approx_traffic TEXT,
            traffic_score INTEGER DEFAULT 0,
            seo_title TEXT,
            meta_description TEXT,
            article_body TEXT,
            image_url TEXT,
            source_links TEXT,
            status TEXT NOT NULL DEFAULT 'published',
            published_at TEXT,
            created_at TEXT NOT NULL,
            trend_pub_date TEXT,
            h1 TEXT,
            faq_json TEXT,
            seo_keywords TEXT
        );
        INSERT INTO trending_topics_mig ({col_list})
        SELECT {col_list} FROM trending_topics;
        DROP TABLE trending_topics;
        ALTER TABLE trending_topics_mig RENAME TO trending_topics;
        CREATE INDEX IF NOT EXISTS idx_trending_published ON trending_topics(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_trending_norm ON trending_topics(keyword_normalized);
        """
    )
    conn.commit()


def normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.lower().split())


def unique_trending_slug(conn: sqlite3.Connection, keyword: str) -> str:
    base = slugify(keyword)
    if not base:
        base = "trending"
    # Slug must contain the keyword phrase (user SEO requirement).
    candidate = base
    n = 2
    while conn.execute("SELECT 1 FROM trending_topics WHERE slug = ?", (candidate,)).fetchone():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def count_by_normalized(conn: sqlite3.Connection, keyword_normalized: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM trending_topics WHERE keyword_normalized = ?",
        (keyword_normalized,),
    ).fetchone()
    return int(row["n"]) if row else 0


def latest_by_normalized(conn: sqlite3.Connection, keyword_normalized: str):
    return conn.execute(
        """
        SELECT * FROM trending_topics
        WHERE keyword_normalized = ?
        ORDER BY published_at DESC, id DESC
        LIMIT 1
        """,
        (keyword_normalized,),
    ).fetchone()


def insert_topic(conn: sqlite3.Connection, row: dict) -> int:
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" * len(row))
    cur = conn.execute(
        f"INSERT INTO trending_topics ({cols}) VALUES ({placeholders})",
        tuple(row.values()),
    )
    conn.commit()
    return int(cur.lastrowid)


def all_published(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT slug, published_at FROM trending_topics
        WHERE status = 'published' AND article_body IS NOT NULL
        ORDER BY published_at DESC, id DESC
        """
    ).fetchall()


def published_topics(conn: sqlite3.Connection, limit: int | None = None):
    q = """
        SELECT * FROM trending_topics
        WHERE status = 'published' AND article_body IS NOT NULL AND slug IS NOT NULL
        ORDER BY published_at DESC, traffic_score DESC, id DESC
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")