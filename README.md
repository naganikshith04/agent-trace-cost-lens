# agent-trace-cost-lens

## What it does

A local dashboard that turns your LLM agent traces into token, latency and failure insights.

- Imports agent-run traces in one custom JSON format (`ollama-agent-trace` v1, defined in this repo) into SQLite, atomically and idempotently. Ollama itself does not export this format; there is no native Ollama trace exporter. A small converter (`python -m trace_lens convert-ollama chat.jsonl --run-id my-run --out trace.json`) turns saved Ollama `/api/chat` JSONL responses into flat `llm` steps (no tool or parent/child structure).
- FastAPI endpoints return per-run metrics: tokens, total and per-step latency, error counts.
- A Next.js trace tree shows steps in parent/child order and flags failed steps and steps slower than a configurable threshold.
- A failure tagger asks a local Ollama model to classify why a step failed, with an evaluation harness over 40 labeled examples.

Built with AI assistance.

## Quickstart

```bash
# Python 3.12 (the version CI pins; the timestamp parsing is version-independent)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                           # no network or Ollama needed

python -m trace_lens import examples/sample_trace.json
python -m trace_lens serve                       # http://127.0.0.1:8000

cd web && npm install
NEXT_PUBLIC_SLOW_MS=5000 npm run dev             # http://127.0.0.1:3000
npm test                                         # component + page tests (Node 20, see web/.nvmrc; use `npm ci`)
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

Measured run with model `llama3.2` and the current tagger prompt (the one with the fuller `invalid_output` definition and four illustrative examples): **accuracy 0.900 (36/40)**, details in `eval_results.json`.

| gold tag | correct |
| --- | --- |
| timeout | 7/8 |
| tool_error | 8/8 |
| invalid_output | 8/8 |
| context_overflow | 8/8 |
| model_unavailable | 5/8 |

**Limit of this number:** the 40 items are hand-written, synthetic error strings, and the tagger only sees the step name, kind and error text. The 90% therefore measures how well the model reads invented messages, not how well it diagnoses real agent failures. The prompt was extended after seeing the weak `invalid_output` class on this same set, so the improvement on these 40 items is partly tuned to them; the held-out set below is the fairer check.

The 4 misses, by item id (gold → predicted), from `eval_results.json`: t05 `timeout` → `context_overflow`; t33 `model_unavailable` → `tool_error`; t36 `model_unavailable` → `timeout`; t38 `model_unavailable` → `tool_error`. `model_unavailable` is now the weakest class (3 of 8 wrong), so treat that tag as less reliable. The tagger still sees only the step name, kind and error text, not parent-step context.

### Baseline and hard cases

`keyword_tag` in `trace_lens/tagger.py` is an offline keyword-rule baseline over the same error text. `scripts/eval_tagger.py` prints its accuracy on the 40 items next to the model's, and also runs both on `eval/hard_cases.jsonl`, 8 further ambiguous, real-world-style error strings (e.g. wrapped library exceptions) kept separate from the 40. Measured results from the same run:

| set | `llama3.2` | keyword rules |
| --- | --- | --- |
| 40 labeled items | 36/40 (0.900) | 33/40 (0.825) |
| 8 hard cases | 5/8 | 3/8 |
| 32 held-out items (`eval/heldout.jsonl`) | 29/32 (0.91) | 14/32 (0.44) |

**Conclusion:** the model beats the keyword rules on the 40 tuned items (36/40 vs 33/40) and by a wide margin on unseen phrasing (29/32 vs 14/32 held-out). The held-out set was written after the keyword rules were frozen, so it is the fairer comparison and the strongest result here. The 8 hard cases point the same way (5/8 vs 3/8) but are too few to support a claim alone. The held-out counts are saved in `eval_heldout_results.json` as aggregates only (the committed file was updated by hand to the 29/32 figure from the latest run output), so the held-out figures cannot yet be audited item by item: per-item predictions were not captured in that run. `scripts/eval_tagger.py` writes per-item predictions for both the model (`eval_heldout_results.json`) and the keyword rules (`eval_heldout_keyword_results.json`) on its next run, which will replace the aggregate-only file. The held-out items are still hand-written, so this is not a measure on real agent failures.

**Caveat on the baseline:** the keyword rules were written with the labeled set in view (words such as "budget", "refused" and "inference host" come from those strings), so the baseline score is probably inflated. The rule order is also brittle: the bare word "model" maps to `model_unavailable`, so "model returned empty JSON" is tagged `model_unavailable` (pinned in `tests/test_evaluation.py` as a known misfire).

To reproduce (needs a running Ollama with the model pulled):

```bash
OLLAMA_MODEL=llama3.2 python scripts/eval_tagger.py
```

The pytest suite tests the harness and the `?method=llm` API path with a mocked LLM and never contacts Ollama.

**What the UI shows:** the Failure summary panel has a **Keyword / LLM** toggle. Keyword (offline rules) is the default; LLM calls the local Ollama model through `GET /runs/{id}/tags?method=llm`, and shows a message if Ollama is not reachable. Because the held-out results favour the model (29/32 vs 14/32), use the **LLM** toggle when Ollama is running; the keyword default is kept only because it works offline and instantly. The keyword rules are the weaker tagger on unseen text, and the rule order is not fixed here: changing it would invalidate the measured keyword scores above.

The UI states can be previewed without data: open the page with `?state=loading`, `?state=empty` or `?state=error`. The page logic (loading, empty, error with Retry, and the tagging toggle) is covered by vitest tests with a mocked `fetch` in `web/tests/page.test.jsx`.

Note: step error text is untrusted and is interpolated into the tagger prompt, so it is a low-risk prompt-injection surface. Before it reaches the prompt it is flattened to one line (control characters and line breaks removed) and cut to 500 characters. The reply is only used as a tag, and `parse_tag` restricts it to the five tags or `unknown`. To bound latency, `?method=llm` sends each distinct error string to Ollama once per request and at most 10 distinct strings (`MAX_LLM_TAGS` in `trace_lens/api.py`); further failed steps are tagged `unknown`.

## Limitations

- Note that only one JSON format is supported in v1 (`ollama-agent-trace` version `1`); other formats are rejected. No adapter exists for agent frameworks or OpenTelemetry spans; only the `/api/chat` JSONL converter above is provided.
- Steps must list parents before children; timestamps need a timezone.
- The UI badge uses the offline keyword tagger by default; the Keyword/LLM toggle switches to the Ollama tagger (`?method=llm`). Tags are computed on request, not stored.
- Re-importing a run_id with different content raises a conflict instead of overwriting; runs imported before this check have no stored hash and are skipped silently.
- No authentication; intended for local use only.
