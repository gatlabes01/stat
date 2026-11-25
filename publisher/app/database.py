import sqlite3
from pathlib import Path

from app.paths import project_root

DB_PATH = project_root() / "data" / "stories.db"

SCHEMA_COLUMNS = [
    ("source_title", "TEXT"),
    ("slug", "TEXT"),
    ("seo_title", "TEXT"),
    ("meta_description", "TEXT"),
    ("keywords", "TEXT"),
    ("article_body", "TEXT"),
    ("image_alt", "TEXT"),
    ("status", "TEXT NOT NULL DEFAULT 'pending'"),
    ("enriched_at", "TEXT"),
    ("error_message", "TEXT"),
    ("images_json", "TEXT"),
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(stories)").fetchall()
    }
    for name, typedef in SCHEMA_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE stories ADD COLUMN {name} {typedef}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_stories_slug ON stories(slug) WHERE slug IS NOT NULL"
    )
    conn.execute(
        """
        UPDATE stories SET source_title = title
        WHERE source_title IS NULL AND title IS NOT NULL
        """
    )
    conn.execute(
        """
        UPDATE stories SET status = 'pending'
        WHERE status IS NULL OR (status = 'published' AND article_body IS NULL)
        """
    )
    conn.execute(
        """
        UPDATE stories SET status = 'pending'
        WHERE status = 'published' AND images_json IS NULL
        """
    )
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            author TEXT,
            published_at TEXT,
            image_url TEXT,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stories_published ON stories(published_at DESC)"
    )
    conn.commit()
    _migrate(conn)


def upsert_story(conn: sqlite3.Connection, story: dict) -> tuple[int, bool]:
    existing = conn.execute(
        "SELECT id FROM stories WHERE guid = ?", (story["guid"],)
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE stories SET
                title = :title,
                link = :link,
                summary = COALESCE(:summary, summary),
                author = COALESCE(:author, author),
                published_at = :published_at,
                image_url = COALESCE(:image_url, image_url),
                source_title = COALESCE(source_title, :title)
            WHERE guid = :guid
            """,
            story,
        )
        conn.commit()
        return int(existing["id"]), False

    cur = conn.execute(
        """
        INSERT INTO stories (
            guid, title, link, summary, author, published_at, image_url, source_title, status
        )
        VALUES (
            :guid, :title, :link, :summary, :author, :published_at, :image_url, :title, 'pending'
        )
        """,
        story,
    )
    conn.commit()
    return int(cur.lastrowid), True


def list_published_stories(
    conn: sqlite3.Connection, limit: int = 100, offset: int = 0
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM stories
        WHERE status = 'published' AND article_body IS NOT NULL
        ORDER BY published_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()


def get_story_by_id(conn: sqlite3.Connection, story_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()


def get_story_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stories WHERE slug = ? AND status = 'published'",
        (slug,),
    ).fetchone()


def count_published_stories(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM stories WHERE status = 'published' AND article_body IS NOT NULL"
    ).fetchone()
    return int(row["n"])


def ids_needing_enrichment(conn: sqlite3.Connection, limit: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT id FROM stories
        WHERE (
            status IN ('pending', 'failed')
            OR article_body IS NULL
            OR images_json IS NULL
            OR seo_title LIKE '%| Detailz'
            OR (source_title IS NOT NULL AND seo_title IS NOT NULL
                AND trim(seo_title) != trim(source_title))
        )
        ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                 published_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def all_published_slugs(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return conn.execute(
        """
        SELECT slug, published_at FROM stories
        WHERE status = 'published' AND slug IS NOT NULL
        ORDER BY published_at DESC
        """
    ).fetchall()