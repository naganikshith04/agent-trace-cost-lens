"""Ties the committed held-out result files to per-item predictions.

The model file is currently aggregate-only (see README), so its per-item check
is skipped until scripts/eval_tagger.py is re-run and the per-item files are
committed. Once they exist, the counts are recomputed here and must match.
"""
import json
from pathlib import Path

import pytest

from trace_lens.evaluation import load_heldout

ROOT = Path(__file__).resolve().parent.parent
MODEL_FILE = ROOT / "eval_heldout_results.json"
KEYWORD_FILE = ROOT / "eval_heldout_keyword_results.json"


def _check_per_item(path):
    if not path.exists():
        pytest.skip(f"{path.name} not committed yet")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "predictions" not in data:
        pytest.skip(f"{path.name} is aggregate-only; per-item predictions not committed")
    held = {it["id"]: it["label"] for it in load_heldout()}
    preds = data["predictions"]
    assert {p["id"] for p in preds} == set(held)
    assert all(p["gold"] == held[p["id"]] for p in preds)
    recomputed = sum(1 for p in preds if p["predicted"] == p["gold"])
    assert data["total"] == len(held)
    assert data["correct"] == recomputed


def test_model_heldout_counts_match_per_item_predictions():
    _check_per_item(MODEL_FILE)


def test_keyword_heldout_counts_match_per_item_predictions():
    _check_per_item(KEYWORD_FILE)
