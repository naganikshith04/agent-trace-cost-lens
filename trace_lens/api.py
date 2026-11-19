"""FastAPI app exposing run metrics."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from . import metrics
from .db import connect, get_db_path

RUN_ID_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def create_app(db_path: str | None = None) -> FastAPI:
    path = db_path or get_db_path()
    app = FastAPI(title="agent-trace-cost-lens")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def _require(conn, run_id: str) -> None:
        if not metrics.run_exists(conn, run_id):
            raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")

    @app.get("/runs")
    def list_runs() -> list[dict]:
        conn = connect(path)
        try:
            rows = conn.execute(
                "SELECT run_id, model, task, started_at FROM runs ORDER BY started_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @app.get("/runs/{run_id}/metrics")
    def get_metrics(run_id: str = Path(pattern=RUN_ID_PATTERN)) -> dict:
        conn = connect(path)
        try:
            _require(conn, run_id)
            return metrics.run_metrics(conn, run_id)
        finally:
            conn.close()

    @app.get("/runs/{run_id}/tree")
    def get_tree(run_id: str = Path(pattern=RUN_ID_PATTERN)) -> list[dict]:
        conn = connect(path)
        try:
            _require(conn, run_id)
            return metrics.run_tree(conn, run_id)
        finally:
            conn.close()

    return app


def app_factory() -> FastAPI:
    return create_app()
