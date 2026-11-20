import json

from trace_lens.evaluation import evaluate, load_dataset, load_heldout
from trace_lens.tagger import TAGS, make_tagger, parse_tag


def test_heldout_set_has_30_plus_unique_items_covering_all_tags():
    held = load_heldout()
    main_ids = {it["id"] for it in load_dataset()}
    assert len(held) >= 30
    assert len({it["id"] for it in held}) == len(held)
    assert not main_ids & {it["id"] for it in held}
    assert set(it["label"] for it in held) == set(TAGS)


def test_dataset_has_40_labeled_entries():
    items = load_dataset()
    assert len(items) == 40
    assert all(it["label"] for it in items)
    assert len({it["id"] for it in items}) == 40
    assert set(it["label"] for it in items) == set(TAGS)


def test_accuracy_is_correct_over_40(tmp_path):
    items = load_dataset()
    gold = {it["error"]: it["label"] for it in items}
    wrong = {items[0]["error"], items[1]["error"], items[2]["error"]}

    def fake_generate(prompt):
        error = prompt.split("Error message: ")[1].split("\n")[0]
        return "tool_error" if error in wrong and gold[error] != "tool_error" else gold[error]

    out = tmp_path / "res.json"
    result = evaluate(make_tagger(fake_generate), out_path=out)
    assert result["total"] == 40
    assert result["correct"] == 37
    assert result["accuracy"] == 37 / 40
    assert json.loads(out.read_text(encoding="utf-8"))["accuracy"] == 37 / 40
    assert len(result["predictions"]) == 40


def test_keyword_baseline_runs_offline():
    from trace_lens.evaluation import load_hard_cases
    from trace_lens.tagger import keyword_tag

    result = evaluate(keyword_tag)
    assert result["total"] == 40
    assert 0 <= result["accuracy"] <= 1
    assert keyword_tag({"error": "prompt is too long: 9120 tokens"}) == "context_overflow"
    assert keyword_tag({"error": "zzz"}) == "unknown"
    hard = load_hard_cases()
    assert len(hard) == 8 and {h["id"] for h in hard}.isdisjoint(i["id"] for i in load_dataset())


def test_keyword_rule_order_known_misfire():
    from trace_lens.tagger import keyword_tag

    # Documents a known weakness: the bare word "model" is matched before the
    # JSON/empty-output rule, so malformed model output is tagged model_unavailable.
    assert keyword_tag({"error": "model returned empty JSON"}) == "model_unavailable"
    # Without the word "model" the invalid_output rule applies as intended.
    assert keyword_tag({"error": "returned empty JSON"}) == "invalid_output"


def test_parse_tag():
    assert parse_tag("  Timeout.\n") == "timeout"
    assert parse_tag("I think it is context_overflow") == "context_overflow"
    assert parse_tag("banana") == "unknown"
