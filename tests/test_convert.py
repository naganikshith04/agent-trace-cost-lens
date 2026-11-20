import json

import pytest

from trace_lens.convert import convert_ollama_log
from trace_lens.schema import TraceValidationError, validate_trace


def test_convert_chat_log(tmp_path):
    log = tmp_path / "chat.jsonl"
    rows = [
        {"model": "llama3.2", "created_at": "2025-01-01T10:00:03.123456789Z", "done": True,
         "total_duration": 3_000_000_000, "prompt_eval_count": 12, "eval_count": 7},
        {"model": "llama3.2", "created_at": "2025-01-01T10:00:09Z", "done": True,
         "total_duration": 1_000_000_000, "error": "model requires more system memory"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    doc = validate_trace(convert_ollama_log(log, "chat-1"))
    assert doc["model"] == "llama3.2"
    assert [s["status"] for s in doc["steps"]] == ["ok", "error"]
    assert doc["steps"][0]["prompt_tokens"] == 12 and doc["steps"][0]["completion_tokens"] == 7


def test_convert_rejects_empty(tmp_path):
    log = tmp_path / "empty.jsonl"
    log.write_text("\n", encoding="utf-8")
    with pytest.raises(TraceValidationError):
        convert_ollama_log(log, "x")
