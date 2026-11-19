# agent-trace-cost-lens

## What it does

A local dashboard that turns your LLM agent traces into token, latency and failure insights.

- Imports Ollama agent-run traces (one JSON format) into SQLite, atomically and idempotently.
- FastAPI endpoints return per-run metrics: tokens, total and per-step latency, error counts.
- A Next.js trace tree shows steps in parent/child order and flags failed steps and steps slower than a configurable threshold.
- A failure tagger asks a local Ollama model to classify why a step failed, with an evaluation harness over 40 labeled examples.

Built with AI assistance.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                           # no network or Ollama needed

python -m trace_lens import examples/sample_trace.json
python -m trace_lens serve                       # http://127.0.0.1:8000

cd web && npm install
NEXT_PUBLIC_SLOW_MS=5000 npm run dev             # http://127.0.0.1:3000
npm test                                         # component test
```

Environment variables are listed in `.env.example` (`TRACE_DB_PATH`, `OLLAMA_URL`, `OLLAMA_MODEL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SLOW_MS`). Services bind to 127.0.0.1.

### Trace schema (v1)

Defined in `schema/trace_v1.schema.json` and shared by the importer and tests. A run has `format` (`ollama-agent-trace`), `version` (`1`), `run_id`, `model`, `started_at`, optional `task`, and `steps`. Each step has `step_id`, optional `parent_id` (must reference an earlier step), `name`, `kind` (`agent|llm|tool`), timezone-aware `started_at`/`ended_at`, `prompt_tokens`, `completion_tokens`, `status` (`ok|error`) and optional `error`. See `examples/sample_trace.json`.

## Architecture

```
trace JSON -> schema.py (validate) -> importer.py -> SQLite (runs, steps)
                                                        |
                          metrics.py <------------------+
                              |
                         api.py (FastAPI) -> web/ (Next.js trace tree)

tagger.py (Ollama) + evaluation.py + eval/labeled_traces.jsonl  -> scripts/eval_tagger.py
```

Validation runs fully before any write, and inserts happen in one transaction, so a bad file never leaves partial rows. Total latency is the wall-clock span of the run, so nested steps are not double counted; the sum of step durations is reported separately.

## Beyond the original

The inspiration was a Show HN post about Faros Desktop, a local app for viewing AI traces (not verified here; see the original post). This project goes in a different direction and aims to be more useful for people running their own local agents:

- **Evaluated failure tagger**: failed steps can be classified into five causes by a local Ollama model, and the tagger ships with a reproducible accuracy evaluation on 40 labeled cases rather than unmeasured claims.
- **Strict, documented schema** with atomic, idempotent import: re-importing is safe and invalid files are rejected with a clear message and no partial writes.
- **Slow-step flagging** with a configurable threshold directly in the trace tree, not only totals.
- **Fully local and free**: SQLite, a local Ollama model, no account or paid API.

## Evaluation

The tagger (`trace_lens/tagger.py`) sends the step name, kind and error message to a local Ollama model and maps the reply to one of: `timeout`, `tool_error`, `invalid_output`, `context_overflow`, `model_unavailable`. The harness (`trace_lens/evaluation.py`) runs it over exactly 40 hand-written labeled examples in `eval/labeled_traces.jsonl` (8 per tag) and reports tag accuracy = correct predictions / 40, plus per-item predictions in `eval_results.json`.

The labeled examples are synthetic and written by hand; they are not real production traces. Results are added after the first real run; none are reported yet. To reproduce (needs a running Ollama with the model pulled):

```bash
OLLAMA_MODEL=llama3.2 python scripts/eval_tagger.py
```

The pytest suite tests the harness with a mocked LLM and never contacts Ollama.

Note: step error text is untrusted and is interpolated into the tagger prompt, so it is a low-risk prompt-injection surface. The reply is only used as a tag, and `parse_tag` restricts it to the five tags or `unknown`.

## Limitations

- Note that only one JSON format is supported in v1 (`ollama-agent-trace` version `1`); other formats are rejected.
- Steps must list parents before children; timestamps need a timezone.
- The failure tagger is a Python API plus evaluation script; it is not yet wired into the API or UI.
- No authentication; intended for local use only.
