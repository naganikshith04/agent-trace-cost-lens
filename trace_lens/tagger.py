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


def make_tagger(generate: Callable[[str], str]) -> Callable[[dict], str]:
    """Build a tagging function from any text-generation callable (real or mocked)."""

    def tag(item: dict) -> str:
        prompt = PROMPT.format(
            step_name=item.get("step_name", ""),
            kind=item.get("kind", ""),
            error=item.get("error", ""),
        )
        return parse_tag(generate(prompt))

    return tag
