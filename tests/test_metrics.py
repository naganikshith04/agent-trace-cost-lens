from trace_lens.importer import import_trace
from trace_lens.metrics import run_metrics, run_tree


def test_metrics_hand_computed(conn, sample_doc):
    import_trace(conn, sample_doc)
    m = run_metrics(conn, "run-001")
    assert m["total_tokens"] == 450
    assert m["prompt_tokens"] == 320
    assert m["completion_tokens"] == 130
    assert m["total_latency_ms"] == 10000
    assert m["step_latency_sum_ms"] == 20000
    assert m["error_count"] == 1
    assert m["step_count"] == 4
    assert [s["duration_ms"] for s in m["steps"]] == [10000, 3000, 6000, 1000]


def test_zero_failed_steps(conn, sample_doc):
    sample_doc["steps"][2]["status"] = "ok"
    sample_doc["steps"][2]["error"] = None
    import_trace(conn, sample_doc)
    assert run_metrics(conn, "run-001")["error_count"] == 0


def test_run_with_no_steps(conn, sample_doc):
    sample_doc["steps"] = []
    import_trace(conn, sample_doc)
    m = run_metrics(conn, "run-001")
    assert m["total_tokens"] == 0
    assert m["total_latency_ms"] == 0
    assert m["error_count"] == 0
    assert m["steps"] == []


def test_tree_order_and_parents(conn, sample_doc):
    import_trace(conn, sample_doc)
    tree = run_tree(conn, "run-001")
    assert [t["step_id"] for t in tree] == ["s1", "s2", "s3", "s4"]
    assert tree[0]["parent_id"] is None
    assert tree[2]["status"] == "error"
