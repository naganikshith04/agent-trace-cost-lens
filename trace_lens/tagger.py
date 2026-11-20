"""LLM failure tagger backed by a local Ollama server."""
from __future__ import annotations

import os
from typing import Callable

import httpx

TAGS = ["timeout", "tool_error", "invalid_output", "context_overflow", "model_unavailable"]
UNKNOWN = "unknown"

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2"

PROMPT = """You classify failures of steps in an LLM agent run.
Allowed tags:
- timeout: the step ran out of time or a request timed out
- tool_error: a tool or external command/API failed
- invalid_output: the model output was malformed or failed validation
- context_overflow: the prompt exceeded the context window or token limit
- model_unavailable: the model could not be loaded, found or reached

Step name: {step_name}
Step kind: {kind}
Error message: {error}

Answer with exactly one tag and nothing else."""


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 60.0):
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0}},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return str(resp.json().get("response", ""))


def parse_tag(text: str) -> str:
    low = text.strip().lower()
    hits = [(low.find(t), t) for t in TAGS if t in low]
    return min(hits)[1] if hits else UNKNOWN


# Ordered keyword rules: the first rule with a matching substring wins.
KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("context_overflow", ("context window", "context length", "context size", "num_ctx",
                          "too many tokens", "token limit", "too long", "sequence length")),
    ("model_unavailable", ("model", "ollama", "inference host", "loading")),
    ("timeout", ("timed out", "timeout", "deadline", "time limit", "budget")),
    ("invalid_output", ("json", "schema", "parse", "validation", "malformed", "empty response")),
    ("tool_error", ("tool", "exit", "status", "permission", "not found", "no such", "refused",
                    "error")),
]


def keyword_tag(item: dict) -> str:
    """Offline baseline: substring rules over the error text only (no LLM)."""
    text = str(item.get("error", "")).lower()
    for tag, words in KEYWORD_RULES:
        if any(w in text for w in words):
            return tag
    return UNKNOWN


MAX_FIELD_CHARS = 500


def sanitize_field(value: object, limit: int = MAX_FIELD_CHARS) -> str:
    """Make untrusted text safe to place on one prompt line: no control chars or
    line breaks (so it cannot fake a new prompt section), bounded length."""
    text = "".join(ch if ch.isprintable() else " " for ch in str(value))
    return " ".join(text.split())[:limit]


def make_tagger(generate: Callable[[str], str]) -> Callable[[dict], str]:
    """Build a tagging function from any text-generation callable (real or mocked)."""

    def tag(item: dict) -> str:
        prompt = PROMPT.format(
            step_name=sanitize_field(item.get("step_name", ""), 120),
            kind=sanitize_field(item.get("kind", ""), 20),
            error=sanitize_field(item.get("error", "")),
        )
        return parse_tag(generate(prompt))

    return tag
