import pytest
from fastapi.testclient import TestClient

from trace_lens.api import create_app
from trace_lens.importer import import_trace
from trace_lens.metrics import run_metrics


@pytest.fixture
def client(conn, db_path, sample_doc):
    import_trace(conn, sample_doc)
    return TestClient(create_app(db_path))


def test_metrics_endpoint_matches_functions(client, conn):
    resp = client.get("/runs/run-001/metrics")
    assert resp.status_code == 200
    assert resp.json() == run_metrics(conn, "run-001")
    assert resp.json()["total_tokens"] == 450


def test_unknown_run_404(client):
    assert client.get("/runs/nope/metrics").status_code == 404
    assert client.get("/runs/nope/tree").status_code == 404


def test_invalid_run_id_rejected(client):
    assert client.get("/runs/bad$id/metrics").status_code == 422


def test_tags_endpoint_tags_failed_steps_only(client):
    resp = client.get("/runs/run-001/tags")
    assert resp.status_code == 200
    tags = resp.json()
    assert [t["step_id"] for t in tags] == ["s3"]
    assert tags[0]["method"] == "keyword"
    assert tags[0]["tag"] in {"tool_error", "model_unavailable", "timeout", "invalid_output",
                              "context_overflow", "unknown"}
    assert client.get("/runs/nope/tags").status_code == 404
    assert client.get("/runs/run-001/tags?method=bogus").status_code == 422


def test_tags_endpoint_llm_method_with_mocked_client(client, monkeypatch):
    import trace_lens.tagger as tagger

    seen = {}

    class FakeClient:
        def generate(self, prompt):
            seen["prompt"] = prompt
            return "timeout"

    monkeypatch.setattr(tagger, "OllamaClient", FakeClient)
    resp = client.get("/runs/run-001/tags?method=llm")
    assert resp.status_code == 200
    assert resp.json() == [{"step_id": "s3", "tag": "timeout", "method": "llm"}]
    assert "tool failed: connection refused" in seen["prompt"]


def test_tags_endpoint_llm_failure_is_502(client, monkeypatch):
    import trace_lens.tagger as tagger

    class DownClient:
        def generate(self, prompt):
            raise RuntimeError("ollama down")

    monkeypatch.setattr(tagger, "OllamaClient", DownClient)
    assert client.get("/runs/run-001/tags?method=llm").status_code == 502


def test_list_runs_and_tree(client):
    runs = client.get("/runs").json()
    assert [r["run_id"] for r in runs] == ["run-001"]
    tree = client.get("/runs/run-001/tree").json()
    assert len(tree) == 4
    assert tree[2]["error"] == "tool failed: connection refused"
