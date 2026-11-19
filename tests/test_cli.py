import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample_trace.json"


def test_python_m_trace_lens_import(tmp_path):
    db = tmp_path / "cli.db"
    cmd = [sys.executable, "-m", "trace_lens", "import", str(SAMPLE), "--db", str(db)]
    first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "imported" in first.stdout
    second = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert "skipped" in second.stdout
