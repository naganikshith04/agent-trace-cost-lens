import json
from pathlib import Path

from trace_lens import importer, schema

ROOT = Path(__file__).resolve().parent.parent


def test_importer_version_matches_schema_file():
    on_disk = json.loads((ROOT / "schema" / "trace_v1.schema.json").read_text(encoding="utf-8"))
    assert importer.ACCEPTED_VERSION == on_disk["version"] == schema.SUPPORTED_VERSION
    assert schema.SUPPORTED_FORMAT == on_disk["format"]


def test_sample_uses_schema_version(sample_doc):
    assert sample_doc["version"] == schema.SUPPORTED_VERSION
    assert sample_doc["format"] == schema.SUPPORTED_FORMAT


def test_readme_states_single_format():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "only one JSON format is supported in v1" in readme
