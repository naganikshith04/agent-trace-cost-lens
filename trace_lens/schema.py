"""Trace schema v1: loading the shared definition and validating documents."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "trace_v1.schema.json"

ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class TraceValidationError(ValueError):
    """Raised when a trace document does not match the supported format."""


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


SCHEMA = load_schema()
SUPPORTED_FORMAT: str = SCHEMA["format"]
SUPPORTED_VERSION: str = SCHEMA["version"]


def parse_ts(value: Any, where: str) -> datetime:
    if not isinstance(value, str):
        raise TraceValidationError(f"{where}: timestamp must be a string")
    try:
        # "Z" is accepted by fromisoformat only on Python >= 3.11; normalise it for 3.8-3.10.
        ts = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc:
        raise TraceValidationError(f"{where}: invalid ISO 8601 timestamp {value!r}") from exc
    if ts.tzinfo is None:
        raise TraceValidationError(f"{where}: timestamp must include a timezone")
    return ts


def _need_str(obj: dict, key: str, where: str, *, ident: bool = False) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val:
        raise TraceValidationError(f"{where}: '{key}' must be a non-empty string")
    if ident and not ID_RE.match(val):
        raise TraceValidationError(f"{where}: '{key}' has invalid characters or length")
    return val


def _need_tokens(obj: dict, key: str, where: str) -> int:
    val = obj.get(key)
    if isinstance(val, bool) or not isinstance(val, int) or val < 0:
        raise TraceValidationError(f"{where}: '{key}' must be a non-negative integer")
    return val


def validate_trace(doc: Any) -> dict[str, Any]:
    """Validate a decoded trace document; return it unchanged or raise."""
    if not isinstance(doc, dict):
        raise TraceValidationError("trace must be a JSON object")
    if doc.get("format") != SUPPORTED_FORMAT:
        raise TraceValidationError(
            f"unsupported format {doc.get('format')!r}; expected {SUPPORTED_FORMAT!r}"
        )
    if doc.get("version") != SUPPORTED_VERSION:
        raise TraceValidationError(
            f"unsupported version {doc.get('version')!r}; expected {SUPPORTED_VERSION!r}"
        )
    for key in SCHEMA["run_required"]:
        if key not in doc:
            raise TraceValidationError(f"run: missing required field '{key}'")
    _need_str(doc, "run_id", "run", ident=True)
    _need_str(doc, "model", "run")
    parse_ts(doc["started_at"], "run.started_at")
    steps = doc["steps"]
    if not isinstance(steps, list):
        raise TraceValidationError("run: 'steps' must be a list")

    seen: set[str] = set()
    for i, step in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(step, dict):
            raise TraceValidationError(f"{where}: must be an object")
        for key in SCHEMA["step_required"]:
            if key not in step:
                raise TraceValidationError(f"{where}: missing required field '{key}'")
        sid = _need_str(step, "step_id", where, ident=True)
        if sid in seen:
            raise TraceValidationError(f"{where}: duplicate step_id {sid!r}")
        _need_str(step, "name", where)
        if step["kind"] not in SCHEMA["kinds"]:
            raise TraceValidationError(f"{where}: 'kind' must be one of {SCHEMA['kinds']}")
        if step["status"] not in SCHEMA["statuses"]:
            raise TraceValidationError(f"{where}: 'status' must be one of {SCHEMA['statuses']}")
        start = parse_ts(step["started_at"], f"{where}.started_at")
        end = parse_ts(step["ended_at"], f"{where}.ended_at")
        if end < start:
            raise TraceValidationError(f"{where}: ended_at is before started_at")
        _need_tokens(step, "prompt_tokens", where)
        _need_tokens(step, "completion_tokens", where)
        parent = step.get("parent_id")
        if parent is not None and parent not in seen:
            raise TraceValidationError(f"{where}: parent_id {parent!r} must reference an earlier step")
        for key in ("error", "input", "output"):
            if step.get(key) is not None and not isinstance(step[key], str):
                raise TraceValidationError(f"{where}: '{key}' must be a string or null")
        seen.add(sid)
    return doc
