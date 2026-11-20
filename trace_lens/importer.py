"""Import v1 trace JSON into SQLite, atomically and idempotently."""
from __future__ import annotations

import hashlib
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


class TraceConflictError(TraceValidationError):
    """A run_id is already stored with different content."""


def content_hash(doc: dict) -> str:
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def import_trace(conn: sqlite3.Connection, doc: object) -> bool:
    """Validate and store a trace. Returns True if inserted, False if an identical run exists.

    Raises TraceConflictError if the run_id exists with different content, so the caller
    knows the stored data is stale. Validation happens before any write; the insert runs
    in one transaction.
    """
    validate_trace(doc)
    assert isinstance(doc, dict)
    digest = content_hash(doc)
    row = conn.execute(
        "SELECT content_hash FROM runs WHERE run_id = ?", (doc["run_id"],)
    ).fetchone()
    if row is not None:
        stored = row[0]
        if stored is not None and stored != digest:
            raise TraceConflictError(
                f"run {doc['run_id']!r} is already stored with different content; "
                "stored data is stale (use a new run_id or delete the old run)"
            )
        return False
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, model, task, started_at, content_hash)"
            " VALUES (?, ?, ?, ?, ?)",
            (doc["run_id"], doc["model"], doc.get("task"), doc["started_at"], digest),
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
