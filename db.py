"""SQLite tracking for resumes and sync history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "resume_sync.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    conn.commit()
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            uploaded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sync_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            manual_url TEXT,
            attempted_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_sync_records_resume
            ON sync_records(resume_id);
        """
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_resume(
    conn: sqlite3.Connection,
    *,
    filename: str,
    stored_path: str,
    content_type: str | None,
    size_bytes: int | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO resumes (filename, stored_path, content_type, size_bytes, uploaded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (filename, stored_path, content_type, size_bytes, now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_resumes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM resumes ORDER BY uploaded_at DESC"
    ).fetchall()


def get_resume(conn: sqlite3.Connection, resume_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM resumes WHERE id = ?", (resume_id,)
    ).fetchone()


def add_sync_record(
    conn: sqlite3.Connection,
    *,
    resume_id: int,
    platform: str,
    status: str,
    message: str | None = None,
    manual_url: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO sync_records
            (resume_id, platform, status, message, manual_url, attempted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (resume_id, platform, status, message, manual_url, now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_sync_records(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT sr.*, r.filename
        FROM sync_records sr
        JOIN resumes r ON r.id = sr.resume_id
        ORDER BY sr.attempted_at DESC
        """
    ).fetchall()


def list_sync_records_for_resume(
    conn: sqlite3.Connection, resume_id: int
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM sync_records
        WHERE resume_id = ?
        ORDER BY attempted_at DESC
        """,
        (resume_id,),
    ).fetchall()


def mark_complete(conn: sqlite3.Connection, record_id: int) -> bool:
    cur = conn.execute(
        """
        UPDATE sync_records
        SET status = 'completed', completed_at = ?
        WHERE id = ? AND status = 'manual_required'
        """,
        (now_iso(), record_id),
    )
    conn.commit()
    return cur.rowcount > 0
