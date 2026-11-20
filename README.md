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

This project aims to be useful for people running their own local agents:

- **Evaluated failure tagger**: failed steps are classified into five causes and shown as a badge in the trace tree (`GET /runs/{id}/tags`, offline keyword rules by default, `?method=llm` for a local Ollama model). The tagger ships with a reproducible accuracy evaluation on 40 labeled cases and a keyword baseline rather than unmeasured claims.
- **Visual trace analysis**: waterfall bars per step, token share per step and KPI numerals, with loading, empty and error states.
- **Strict, documented schema** with atomic, idempotent import: re-importing identical content is a no-op, re-importing a run_id with different content is reported as a conflict, and invalid files are rejected with a clear message and no partial writes.
- **Slow-step flagging** with a configurable threshold directly in the trace tree, not only totals.
- **Fully local and free**: SQLite, a local Ollama model, no account or paid API.

## Evaluation

The tagger (`trace_lens/tagger.py`) sends the step name, kind and error message to a local Ollama model and maps the reply to one of: `timeout`, `tool_error`, `invalid_output`, `context_overflow`, `model_unavailable`. The harness (`trace_lens/evaluation.py`) runs it over exactly 40 hand-written labeled examples in `eval/labeled_traces.jsonl` (8 per tag) and reports tag accuracy = correct predictions / 40, plus per-item predictions in `eval_results.json`.

### Result

Measured run with model `llama3.2`: **accuracy 0.825 (33/40)**, details in `eval_results.json`.

| gold tag | correct |
| --- | --- |
| timeout | 7/8 |
| tool_error | 7/8 |
| invalid_output | 4/8 |
| context_overflow | 8/8 |
| model_unavailable | 7/8 |

**Limit of this number:** the 40 items are hand-written, synthetic error strings, and the tagger only sees the step name, kind and error text. The 82.5% therefore measures how well the model reads invented messages, not how well it diagnoses real agent failures.

The 7 misses, by item id (gold → predicted): `invalid_output` is the weak class (4 of 8 wrong). t20 "empty response returned by model" and t23 "truncated JSON: unexpected end of output" → `timeout`; t19 "could not parse tool call from model reply; got free text" and t24 "arguments do not match the function signature: unexpected field 'path2'" → `tool_error`. The other three: t05 `timeout` ("context deadline exceeded while streaming tokens") → `context_overflow`; t14 `tool_error` ("PermissionError: access denied writing to output directory") → `timeout`; t34 `model_unavailable` ("connection refused: is the Ollama server running?", an unreachable server rather than a model-load failure) → `tool_error`. In practice, malformed model output that mentions tools or truncation gets blamed on the tool or on time, so treat `invalid_output` tags as less reliable.

### Baseline and hard cases

`keyword_tag` in `trace_lens/tagger.py` is an offline keyword-rule baseline over the same error text. `scripts/eval_tagger.py` prints its accuracy on the 40 items next to the model's, and also runs both on `eval/hard_cases.jsonl`, 8 further ambiguous, real-world-style error strings (e.g. wrapped library exceptions) kept separate from the 40. Measured results from the same run:

| set | `llama3.2` | keyword rules |
| --- | --- | --- |
| 40 labeled items | 33/40 (0.825) | 33/40 (0.825) |
| 8 hard cases | 5/8 | 3/8 |

**The model only ties the keyword rules on the 40 items**, so the 82.5% headline is no better than offline keyword matching. It beats them only on the 8 hard cases (5/8 vs 3/8), a very small sample that cannot support a strong claim.

**Caveat on the baseline:** the keyword rules were written with the labeled set in view (words such as "budget", "refused" and "inference host" come from those strings), so the baseline score is probably inflated. The rule order is also brittle: the bare word "model" maps to `model_unavailable`, so "model returned empty JSON" is tagged `model_unavailable` (pinned in `tests/test_evaluation.py` as a known misfire).

To reproduce (needs a running Ollama with the model pulled):

```bash
OLLAMA_MODEL=llama3.2 python scripts/eval_tagger.py
```

The pytest suite tests the harness and the `?method=llm` API path with a mocked LLM and never contacts Ollama.

**What the UI shows:** the dashboard badges and failure summary use the offline **keyword** tagger, not the model evaluated at 82.5%. The same keyword rules also scored 82.5% on the 40 items, but the UI tags are not LLM output. The LLM tagger is only reachable through `GET /runs/{id}/tags?method=llm`.

The UI states can be previewed without data: open the page with `?state=loading`, `?state=empty` or `?state=error`.

Note: step error text is untrusted and is interpolated into the tagger prompt, so it is a low-risk prompt-injection surface. The reply is only used as a tag, and `parse_tag` restricts it to the five tags or `unknown`.

## Limitations

- Note that only one JSON format is supported in v1 (`ollama-agent-trace` version `1`); other formats are rejected.
- Steps must list parents before children; timestamps need a timezone.
- The UI badge uses the offline keyword tagger (`/runs/{id}/tags`); the Ollama tagger is available via `?method=llm` but is not called by the UI. Tags are computed on request, not stored.
- Re-importing a run_id with different content raises a conflict instead of overwriting; runs imported before this check have no stored hash and are skipped silently.
- No authentication; intended for local use only.
