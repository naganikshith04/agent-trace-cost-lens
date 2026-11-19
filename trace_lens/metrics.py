"""Metric math for a stored run."""
from __future__ import annotations

import sqlite3
from datetime import datetime


def _steps(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY seq", (run_id,)
    ).fetchall()


def run_exists(conn: sqlite3.Connection, run_id: str) -> bool:
    return conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone() is not None


def total_tokens(steps: list) -> int:
    return sum(s["prompt_tokens"] + s["completion_tokens"] for s in steps)


def error_count(steps: list) -> int:
    return sum(1 for s in steps if s["status"] == "error")


def total_latency_ms(steps: list) -> int:
    """Wall-clock span from earliest start to latest end (nested steps are not double counted)."""
    if not steps:
        return 0
    start = min(datetime.fromisoformat(s["started_at"]) for s in steps)
    end = max(datetime.fromisoformat(s["ended_at"]) for s in steps)
    return round((end - start).total_seconds() * 1000)


def per_step_latency(steps: list) -> list[dict]:
    return [
        {
            "step_id": s["step_id"],
            "name": s["name"],
            "duration_ms": s["duration_ms"],
            "tokens": s["prompt_tokens"] + s["completion_tokens"],
        }
        for s in steps
    ]


def run_metrics(conn: sqlite3.Connection, run_id: str) -> dict:
    steps = _steps(conn, run_id)
    return {
        "run_id": run_id,
        "step_count": len(steps),
        "prompt_tokens": sum(s["prompt_tokens"] for s in steps),
        "completion_tokens": sum(s["completion_tokens"] for s in steps),
        "total_tokens": total_tokens(steps),
        "total_latency_ms": total_latency_ms(steps),
        "step_latency_sum_ms": sum(s["duration_ms"] for s in steps),
        "error_count": error_count(steps),
        "steps": per_step_latency(steps),
    }


def run_tree(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    return [
        {
            "step_id": s["step_id"],
            "parent_id": s["parent_id"],
            "name": s["name"],
            "kind": s["kind"],
            "status": s["status"],
            "error": s["error"],
            "duration_ms": s["duration_ms"],
            "tokens": s["prompt_tokens"] + s["completion_tokens"],
        }
        for s in _steps(conn, run_id)
    ]
