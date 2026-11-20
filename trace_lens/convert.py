"""Convert Ollama /api/chat (or /api/generate) response logs into a v1 trace.

Input is JSON Lines: one final (``"done": true``) Ollama response object per line, e.g. as
saved from ``curl http://127.0.0.1:11434/api/chat``. Each line becomes one flat ``llm`` step.
Used fields: ``model``, ``created_at``, ``total_duration`` (ns), ``prompt_eval_count``,
``eval_count`` and an optional ``error`` string. Ollama does not emit agent/tool structure,
so no parent/child tree or tool steps are produced.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .schema import SUPPORTED_FORMAT, SUPPORTED_VERSION, TraceValidationError


def _ts(value: object, where: str) -> datetime:
    if not isinstance(value, str):
        raise TraceValidationError(f"{where}: 'created_at' must be a string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:  # Ollama emits nanoseconds; datetime accepts at most microseconds
        head, rest = text.split(".", 1)
        n_digits = len(rest) - len(rest.lstrip("0123456789"))
        digits = rest[:n_digits]
        tail = rest[n_digits:]
        text = f"{head}.{digits[:6].ljust(6, '0')}{tail}"
    try:
        ts = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TraceValidationError(f"{where}: invalid created_at {value!r}") from exc
    if ts.tzinfo is None:
        raise TraceValidationError(f"{where}: created_at must include a timezone")
    return ts


def convert_ollama_log(path: str | Path, run_id: str) -> dict:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TraceValidationError(f"cannot read file: {exc}") from exc
    steps = []
    model = ""
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        where = f"line {n}"
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceValidationError(f"{where}: malformed JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise TraceValidationError(f"{where}: must be a JSON object")
        end = _ts(obj.get("created_at"), where)
        dur_ns = obj.get("total_duration", 0)
        if isinstance(dur_ns, bool) or not isinstance(dur_ns, int) or dur_ns < 0:
            raise TraceValidationError(f"{where}: 'total_duration' must be a non-negative integer")
        start = end - timedelta(microseconds=dur_ns // 1000)
        model = model or str(obj.get("model") or "")
        err = obj.get("error")
        step = {
            "step_id": f"c{len(steps) + 1}",
            "parent_id": None,
            "name": "chat",
            "kind": "llm",
            "started_at": start.isoformat(),
            "ended_at": end.isoformat(),
            "prompt_tokens": int(obj.get("prompt_eval_count") or 0),
            "completion_tokens": int(obj.get("eval_count") or 0),
            "status": "error" if err else "ok",
        }
        if err:
            step["error"] = str(err)
        steps.append(step)
    if not steps:
        raise TraceValidationError("no Ollama responses found in file")
    return {
        "format": SUPPORTED_FORMAT,
        "version": SUPPORTED_VERSION,
        "run_id": run_id,
        "model": model or "unknown",
        "started_at": steps[0]["started_at"],
        "steps": steps,
    }
