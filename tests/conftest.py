import copy
import json
from pathlib import Path

import pytest

from trace_lens.db import connect

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_trace.json"


@pytest.fixture
def sample_doc():
    return copy.deepcopy(json.loads(SAMPLE.read_text(encoding="utf-8")))


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    c = connect(db_path)
    yield c
    c.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
