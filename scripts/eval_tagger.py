"""Run the failure-tagger evaluation against a real local Ollama server.

Not part of the pytest suite. Usage: python scripts/eval_tagger.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trace_lens.evaluation import evaluate  # noqa: E402
from trace_lens.tagger import OllamaClient, make_tagger  # noqa: E402


def main() -> int:
    client = OllamaClient()
    try:
        httpx.get(f"{client.base_url}/api/tags", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Ollama not reachable at {client.base_url}: {exc}", file=sys.stderr)
        return 2
    result = evaluate(make_tagger(client.generate), out_path="eval_results.json")
    print(f"model={client.model} accuracy={result['accuracy']:.3f} "
          f"({result['correct']}/{result['total']})")
    print("details written to eval_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
