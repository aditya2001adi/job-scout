"""
SQLite-backed deduplication. Tracks every job URL we've ever seen so we
never send the same job twice. DB file is gitignored.

Dedup uses two keys:
  1. uid (source + URL) — primary key, catches exact URL re-posts
  2. title_co_key (normalized title + company) — secondary key, catches the same job
     posted across multiple locations (different URLs, same role)
"""
import re
import sqlite3
from pathlib import Path
from scrapers.base import Job

DB_PATH = Path(__file__).parent / "jobs.db"


def _normalize_title(title: str) -> str:
    """Strip location/variant suffixes so 'Associate - NYC' == 'Associate - SF'."""
    t = re.sub(r'\s*[-–|]\s*[A-Z][^-–|]{1,40}$', '', title)
    t = re.sub(r'\s*\([^)]{1,50}\)\s*$', '', t)
    return t.lower().strip()


def _title_co_key(job: Job) -> str:
    return f"{_normalize_title(job.title)}||{job.company.lower().strip()}"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            uid TEXT PRIMARY KEY,
            title_co_key TEXT,
            title TEXT,
            company TEXT,
            source TEXT,
            seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add title_co_key column to existing DBs that were created before this change
    try:
        con.execute("ALTER TABLE seen_jobs ADD COLUMN title_co_key TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    con.execute("CREATE INDEX IF NOT EXISTS idx_title_co_key ON seen_jobs (title_co_key)")
    con.commit()
    return con


def filter_new(jobs: list[Job]) -> list[Job]:
    """Return only jobs we haven't seen before (by URL or by title+company)."""
    if not jobs:
        return []
    con = _conn()

    uids = [j.uid for j in jobs]
    uid_placeholders = ",".join("?" * len(uids))
    seen_uids = {row[0] for row in con.execute(
        f"SELECT uid FROM seen_jobs WHERE uid IN ({uid_placeholders})", uids
    )}

    tck_list = [_title_co_key(j) for j in jobs]
    tck_placeholders = ",".join("?" * len(tck_list))
    seen_tcks = {row[0] for row in con.execute(
        f"SELECT title_co_key FROM seen_jobs WHERE title_co_key IN ({tck_placeholders})", tck_list
    )}

    con.close()
    return [j for j in jobs if j.uid not in seen_uids and _title_co_key(j) not in seen_tcks]


def mark_seen(jobs: list[Job]) -> None:
    """Record jobs as seen so they won't appear in future digests."""
    if not jobs:
        return
    con = _conn()
    con.executemany(
        "INSERT OR IGNORE INTO seen_jobs (uid, title_co_key, title, company, source) VALUES (?, ?, ?, ?, ?)",
        [(j.uid, _title_co_key(j), j.title, j.company, j.source) for j in jobs],
    )
    con.commit()
    con.close()


def seen_count() -> int:
    con = _conn()
    (n,) = con.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
    con.close()
    return n
