"""FastAPI app exposing run metrics."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from . import metrics
from .db import connect, get_db_path
from .tagger import keyword_tag

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

    @app.get("/runs/{run_id}/tags")
    def get_tags(
        run_id: str = Path(pattern=RUN_ID_PATTERN),
        method: str = Query("keyword", pattern="^(keyword|llm)$"),
    ) -> list[dict]:
        """Failure tag for each failed step. `keyword` is offline; `llm` asks local Ollama."""
        conn = connect(path)
        try:
            _require(conn, run_id)
            failed = [s for s in metrics.run_tree(conn, run_id) if s["status"] == "error"]
        finally:
            conn.close()
        if method == "llm":
            from .tagger import OllamaClient, make_tagger

            tag_fn = make_tagger(OllamaClient().generate)
        else:
            tag_fn = keyword_tag
        out = []
        for s in failed:
            item = {"step_name": s["name"], "kind": s["kind"], "error": s["error"] or ""}
            try:
                tag = tag_fn(item)
            except Exception as exc:  # Ollama down, bad reply, etc.
                raise HTTPException(status_code=502, detail=f"tagger failed: {exc}") from exc
            out.append({"step_id": s["step_id"], "tag": tag, "method": method})
        return out

    return app


def app_factory() -> FastAPI:
    return create_app()
