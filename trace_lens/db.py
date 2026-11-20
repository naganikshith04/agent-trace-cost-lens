"""SQLite storage."""
from __future__ import annotations

import os
import sqlite3

DEFAULT_DB_PATH = "traces.db"

DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    task TEXT,
    started_at TEXT NOT NULL,
    content_hash TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    step_id TEXT NOT NULL,
    parent_id TEXT,
    seq INTEGER NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    PRIMARY KEY (run_id, step_id)
);
"""


def get_db_path() -> str:
    return os.environ.get("TRACE_DB_PATH", DEFAULT_DB_PATH)


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)")}
    if "content_hash" not in cols:  # databases created before conflict detection
        conn.execute("ALTER TABLE runs ADD COLUMN content_hash TEXT")
        conn.commit()
    return conn
