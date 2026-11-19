import json

from trace_lens.evaluation import evaluate, load_dataset
from trace_lens.tagger import TAGS, make_tagger, parse_tag


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


def test_parse_tag():
    assert parse_tag("  Timeout.\n") == "timeout"
    assert parse_tag("I think it is context_overflow") == "context_overflow"
    assert parse_tag("banana") == "unknown"
