"""Import v1 trace JSON into SQLite, atomically and idempotently."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import SUPPORTED_VERSION, TraceValidationError, parse_ts, validate_trace

ACCEPTED_VERSION = SUPPORTED_VERSION


def load_trace_file(path: str | Path) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TraceValidationError(f"cannot read file: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TraceValidationError(f"malformed JSON: {exc}") from exc


def import_trace(conn: sqlite3.Connection, doc: object) -> bool:
    """Validate and store a trace. Returns True if inserted, False if the run already existed.

    Validation happens before any write; the insert runs in one transaction.
    """
    validate_trace(doc)
    assert isinstance(doc, dict)
    if conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (doc["run_id"],)).fetchone():
        return False
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, model, task, started_at) VALUES (?, ?, ?, ?)",
            (doc["run_id"], doc["model"], doc.get("task"), doc["started_at"]),
        )
        for seq, s in enumerate(doc["steps"]):
            start = parse_ts(s["started_at"], "step")
            end = parse_ts(s["ended_at"], "step")
            duration_ms = round((end - start).total_seconds() * 1000)
            conn.execute(
                "INSERT INTO steps (run_id, step_id, parent_id, seq, name, kind, started_at,"
                " ended_at, duration_ms, prompt_tokens, completion_tokens, status, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc["run_id"], s["step_id"], s.get("parent_id"), seq, s["name"], s["kind"],
                    s["started_at"], s["ended_at"], duration_ms, s["prompt_tokens"],
                    s["completion_tokens"], s["status"], s.get("error"),
                ),
            )
    return True


def import_file(conn: sqlite3.Connection, path: str | Path) -> bool:
    return import_trace(conn, load_trace_file(path))
