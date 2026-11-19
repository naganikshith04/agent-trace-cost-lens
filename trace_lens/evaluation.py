"""Evaluation harness for the failure tagger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .tagger import TAGS

DATASET_PATH = Path(__file__).resolve().parent.parent / "eval" / "labeled_traces.jsonl"
EXPECTED_SIZE = 40


def load_dataset(path: str | Path = DATASET_PATH) -> list[dict]:
    items = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(items) != EXPECTED_SIZE:
        raise ValueError(f"expected {EXPECTED_SIZE} labeled traces, found {len(items)}")
    for it in items:
        if not it.get("label") or it["label"] not in TAGS:
            raise ValueError(f"item {it.get('id')!r} has missing or unknown label")
    return items


def evaluate(tag_fn: Callable[[dict], str], dataset: list[dict] | None = None,
             out_path: str | Path | None = None) -> dict:
    items = dataset if dataset is not None else load_dataset()
    preds = [{"id": it["id"], "gold": it["label"], "predicted": tag_fn(it)} for it in items]
    correct = sum(1 for p in preds if p["gold"] == p["predicted"])
    result = {
        "total": len(items),
        "correct": correct,
        "accuracy": correct / len(items),
        "predictions": preds,
    }
    if out_path:
        Path(out_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
