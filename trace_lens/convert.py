"""Convert Ollama /api/chat (or /api/generate) response logs into a v1 trace.

Input is JSON Lines: one final (``"done": true``) Ollama response object per line, e.g. as
saved from ``curl http://127.0.0.1:11434/api/chat``. Each line becomes one flat ``llm`` step.
Used fields: ``model``, ``created_at``, ``total_duration`` (ns), ``prompt_eval_count``,
``eval_count`` and an optional ``error`` string. Ollama does not emit agent/tool structure,
so no parent/child tree or tool steps are produced.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .schema import SUPPORTED_FORMAT, SUPPORTED_VERSION, TraceValidationError

_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?"
    r"(Z|z|[+-]\d{2}:\d{2})?$"
)


def _ts(value: object, where: str) -> datetime:
    if not isinstance(value, str):
        raise TraceValidationError(f"{where}: 'created_at' must be a string")
    # Parsed with an explicit pattern (not datetime.fromisoformat) so the result does not
    # depend on the Python version: Ollama emits 1-9 fractional digits and a "Z" suffix.
    m = _TS_RE.match(value.strip())
    if not m:
        raise TraceValidationError(f"{where}: invalid created_at {value!r}")
    year, month, day, hour, minute, second, frac, zone = m.groups()
    if zone is None:
        raise TraceValidationError(f"{where}: created_at must include a timezone")
    if zone in ("Z", "z"):
        tz = timezone.utc
    else:
        sign = -1 if zone[0] == "-" else 1
        offset = timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
        tz = timezone(sign * offset)
    micro = int((frac or "").ljust(6, "0")[:6])
    try:
        return datetime(int(year), int(month), int(day), int(hour), int(minute),
                        int(second), micro, tzinfo=tz)
    except ValueError as exc:
        raise TraceValidationError(f"{where}: invalid created_at {value!r}") from exc


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
            "started_at": start.isoformat(timespec="microseconds"),
            "ended_at": end.isoformat(timespec="microseconds"),
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
