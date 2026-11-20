import json

import pytest

from tests.conftest import SAMPLE, count
from trace_lens.importer import import_file, import_trace, load_trace_file
from trace_lens.schema import TraceValidationError


def test_import_valid_fixture(conn, sample_doc):
    assert import_file(conn, SAMPLE) is True
    assert count(conn, "runs") == 1
    assert count(conn, "steps") == 4
    rows = {r["step_id"]: r for r in conn.execute("SELECT * FROM steps")}
    assert rows["s2"]["prompt_tokens"] == 120
    assert rows["s2"]["completion_tokens"] == 80
    assert rows["s2"]["duration_ms"] == 3000
    assert rows["s3"]["status"] == "error"
    assert rows["s3"]["error"] == "tool failed: connection refused"
    assert rows["s3"]["started_at"] == "2025-01-01T10:00:03+00:00"
    assert rows["s2"]["parent_id"] == "s1"


def test_reimport_does_not_duplicate(conn):
    assert import_file(conn, SAMPLE) is True
    assert import_file(conn, SAMPLE) is False
    assert count(conn, "runs") == 1
    assert count(conn, "steps") == 4


def test_reimport_with_different_content_raises(conn, sample_doc):
    from trace_lens.importer import TraceConflictError

    assert import_trace(conn, sample_doc) is True
    sample_doc["steps"][0]["prompt_tokens"] += 1
    with pytest.raises(TraceConflictError, match="different content"):
        import_trace(conn, sample_doc)
    assert count(conn, "runs") == 1


def _assert_rejected_unchanged(conn, doc):
    with pytest.raises(TraceValidationError):
        import_trace(conn, doc)
    assert count(conn, "runs") == 0
    assert count(conn, "steps") == 0


def test_rejects_malformed_file(conn, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(TraceValidationError, match="malformed JSON"):
        import_file(conn, p)
    assert count(conn, "runs") == 0


def test_rejects_missing_required_field(conn, sample_doc):
    del sample_doc["steps"][2]["status"]
    _assert_rejected_unchanged(conn, sample_doc)


def test_rejects_missing_run_field(conn, sample_doc):
    del sample_doc["model"]
    _assert_rejected_unchanged(conn, sample_doc)


def test_rejects_unsupported_format(conn, sample_doc):
    sample_doc["format"] = "other-tracer"
    _assert_rejected_unchanged(conn, sample_doc)


def test_rejects_unsupported_version(conn, sample_doc):
    sample_doc["version"] = "2"
    _assert_rejected_unchanged(conn, sample_doc)


def test_late_error_leaves_no_partial_write(conn, sample_doc):
    sample_doc["steps"][-1]["prompt_tokens"] = -5  # invalid in the last step
    _assert_rejected_unchanged(conn, sample_doc)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["steps"][1].update(parent_id="missing"),
        lambda d: d["steps"][1].update(step_id="s1"),
        lambda d: d["steps"][1].update(ended_at="2024-01-01T00:00:00+00:00"),
        lambda d: d["steps"][1].update(started_at="2025-01-01T10:00:00"),
        lambda d: d["steps"][1].update(kind="weird"),
        lambda d: d["steps"][1].update(prompt_tokens=True),
        lambda d: d.update(run_id="../etc"),
    ],
)
def test_rejects_invalid_values(conn, sample_doc, mutate):
    mutate(sample_doc)
    _assert_rejected_unchanged(conn, sample_doc)


def test_non_object_rejected(conn):
    with pytest.raises(TraceValidationError):
        import_trace(conn, [1, 2])


def test_load_missing_file(tmp_path):
    with pytest.raises(TraceValidationError):
        load_trace_file(tmp_path / "nope.json")


def test_load_trace_file_roundtrip():
    assert json.loads(SAMPLE.read_text(encoding="utf-8")) == load_trace_file(SAMPLE)
