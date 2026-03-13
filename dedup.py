"""
SQLite-backed deduplication. Tracks every job URL we've ever seen so we
never send the same job twice. DB file is gitignored.
"""
import sqlite3
from pathlib import Path
from scrapers.base import Job

DB_PATH = Path(__file__).parent / "jobs.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            uid TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            source TEXT,
            seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    return con


def filter_new(jobs: list[Job]) -> list[Job]:
    """Return only jobs we haven't seen before."""
    if not jobs:
        return []
    con = _conn()
    uids = [j.uid for j in jobs]
    placeholders = ",".join("?" * len(uids))
    seen = {row[0] for row in con.execute(
        f"SELECT uid FROM seen_jobs WHERE uid IN ({placeholders})", uids
    )}
    con.close()
    return [j for j in jobs if j.uid not in seen]


def mark_seen(jobs: list[Job]) -> None:
    """Record jobs as seen so they won't appear in future digests."""
    if not jobs:
        return
    con = _conn()
    con.executemany(
        "INSERT OR IGNORE INTO seen_jobs (uid, title, company, source) VALUES (?, ?, ?, ?)",
        [(j.uid, j.title, j.company, j.source) for j in jobs],
    )
    con.commit()
    con.close()


def seen_count() -> int:
    con = _conn()
    (n,) = con.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
    con.close()
    return n
