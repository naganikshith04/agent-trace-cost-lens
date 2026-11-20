"""Offline checks that the held-out and hard-case sets can be scored per item.

No model results are committed for these sets (see README), so these tests only
exercise the deterministic keyword baseline and never skip.
"""
from trace_lens.evaluation import evaluate, load_hard_cases, load_heldout
from trace_lens.tagger import keyword_tag


def _check(dataset):
    result = evaluate(keyword_tag, dataset=dataset)
    gold = {it["id"]: it["label"] for it in dataset}
    preds = result["predictions"]
    assert {p["id"] for p in preds} == set(gold)
    assert all(p["gold"] == gold[p["id"]] for p in preds)
    assert result["total"] == len(dataset)
    assert result["correct"] == sum(1 for p in preds if p["predicted"] == p["gold"])


def test_keyword_baseline_scores_heldout_per_item():
    _check(load_heldout())


def test_keyword_baseline_scores_hard_cases_per_item():
    _check(load_hard_cases())
