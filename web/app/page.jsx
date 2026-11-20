"use client";
import { useCallback, useEffect, useState } from "react";
import TraceTree, { formatDuration } from "../components/TraceTree.jsx";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const SLOW_MS = Number(process.env.NEXT_PUBLIC_SLOW_MS) || 5000;

async function getJson(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`API returned ${res.status}`);
  return res.json();
}

function Kpi({ label, value, unit, note, bad, hero, index, children }) {
  return (
    <div className={`kpi surface${bad ? " kpi-bad" : ""}${hero ? " kpi-hero" : ""}`} style={{ "--i": index }}>
      <span className="label">{label}</span>
      <span className="value">
        {value}
        {unit && <small className="unit">{unit}</small>}
      </span>
      {children}
      <span className="note">{note}</span>
    </div>
  );
}

function Skeleton() {
  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading traces…</span>
      <div className="kpis" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`surface skeleton sk-kpi${i === 0 ? " kpi-hero" : ""}`} />
        ))}
      </div>
      <div aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="surface skeleton sk-row" />
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  const [runs, setRuns] = useState(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);
  const [tags, setTags] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => {
    setError("");
    setLoading(true);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    // ?state=loading|empty|error previews a UI state without needing the API.
    const preview = new URLSearchParams(window.location.search).get("state");
    if (preview === "loading") return;
    if (preview === "empty") {
      setRuns([]);
      setLoading(false);
      return;
    }
    if (preview === "error") {
      setError("API returned 500");
      setLoading(false);
      return;
    }
    getJson("/runs")
      .then((r) => {
        setRuns(r);
        if (r.length) setSelected((cur) => cur || r[0].run_id);
        else setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [attempt]);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError("");
    const id = encodeURIComponent(selected);
    Promise.all([getJson(`/runs/${id}/metrics`), getJson(`/runs/${id}/tree`)])
      .then(([metrics, tree]) => setDetail({ metrics, tree }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    getJson(`/runs/${id}/tags`)
      .then((list) => setTags(Object.fromEntries(list.map((t) => [t.step_id, t.tag]))))
      .catch(() => setTags({}));
  }, [selected, attempt]);

  const m = detail && detail.metrics;
  const lat = m ? formatDuration(m.total_latency_ms) : null;
  const totalTokens = m ? m.total_tokens : 0;
  const promptPct = totalTokens ? (m.prompt_tokens / totalTokens) * 100 : 0;
  const topSteps = m ? [...m.steps].sort((a, b) => b.tokens - a.tokens).filter((s) => s.tokens > 0) : [];
  const slowestSteps = m ? [...m.steps].sort((a, b) => b.duration_ms - a.duration_ms).slice(0, 4) : [];
  const maxDur = slowestSteps.length ? Math.max(slowestSteps[0].duration_ms, 1) : 1;
  const failedSteps = detail ? detail.tree.filter((s) => s.status === "error") : [];
  const failureCounts = {};
  failedSteps.forEach((s) => {
    const t = tags[s.step_id] || "untagged";
    failureCounts[t] = (failureCounts[t] || 0) + 1;
  });

  return (
    <main>
      <header className="hero" style={{ "--i": 0 }}>
        <span className="mark" aria-hidden="true" />
        <div>
          <h1>Agent trace lens</h1>
          <p className="subtitle">
            Token, latency and failure insights from traces stored locally in SQLite (<code>traces.db</code>).
          </p>
        </div>
      </header>

      {error && (
        <div className="surface panel panel-bad" role="alert">
          <strong>Could not read traces</strong>
          <p>{error}. Is the API running at {API}?</p>
          <button type="button" className="btn" onClick={retry}>Retry</button>
        </div>
      )}

      {loading && !error && <Skeleton />}

      {!loading && !error && runs && runs.length === 0 && (
        <div className="surface panel empty" role="status" style={{ "--i": 1 }}>
          <svg className="icon" viewBox="0 0 24 24" width="40" height="40" aria-hidden="true">
            <path d="M3 12h4l3-8 4 16 3-8h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <strong>No traces yet</strong>
          <p>Point your agent at the importer to get started:</p>
          <code>python -m trace_lens import file.json</code>
        </div>
      )}

      {runs && runs.length > 0 && (
        <div className="picker" style={{ "--i": 1 }}>
          <label htmlFor="run-select" className="label">Run</label>
          <div className="select-wrap">
            <select id="run-select" value={selected} onChange={(e) => setSelected(e.target.value)}>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.model})
                </option>
              ))}
            </select>
            <svg className="chev" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      )}

      {m && !error && (
        <>
          <section className="kpis" aria-label="Run summary">
            <Kpi label="Tokens" value={m.total_tokens.toLocaleString()} index={2} hero
              note={`${m.prompt_tokens.toLocaleString()} prompt · ${m.completion_tokens.toLocaleString()} completion`}>
              <div className="track thin"><div className="fill fill-ok" style={{ width: `${promptPct}%` }} /></div>
            </Kpi>
            <Kpi label="Latency" value={lat.value} unit={lat.unit} index={3}
              note={`${formatDuration(m.step_latency_sum_ms).value} ${formatDuration(m.step_latency_sum_ms).unit} summed over steps`}>
              <div className="track thin">
                <div className="fill fill-warn"
                  style={{ width: `${m.step_latency_sum_ms ? Math.min(100, (m.total_latency_ms / m.step_latency_sum_ms) * 100) : 0}%` }} />
              </div>
            </Kpi>
            <Kpi label="Errors" value={m.error_count} bad={m.error_count > 0} index={4}
              note={`${m.step_count ? Math.round((m.error_count / m.step_count) * 100) : 0}% of steps failed`}>
              <div className="track thin">
                <div className="fill fill-bad" style={{ width: `${m.step_count ? (m.error_count / m.step_count) * 100 : 0}%` }} />
              </div>
            </Kpi>
            <Kpi label="Steps" value={m.step_count} index={5} note="agent, llm and tool calls" />
          </section>

          <div className="columns">
            <aside className="side" aria-label="Insights">
              <div className="surface panel share" style={{ "--i": 6 }}>
                <h2>Token share by step</h2>
                {topSteps.length === 0 && <p className="empty">No tokens recorded.</p>}
                <ul className="share-list">
                  {topSteps.map((s) => (
                    <li key={s.step_id}>
                      <div className="share-row">
                        <span>{s.name}</span>
                        <span className="num">{((s.tokens / totalTokens) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="track"><div className="fill fill-violet" style={{ width: `${(s.tokens / totalTokens) * 100}%` }} /></div>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="surface panel" style={{ "--i": 7 }}>
                <h2>Prompt vs completion</h2>
                <div className="split-row">
                  <span>Prompt <b className="num">{m.prompt_tokens.toLocaleString()}</b></span>
                  <span>Completion <b className="num">{m.completion_tokens.toLocaleString()}</b></span>
                </div>
                <div className="track"><div className="fill fill-ok" style={{ width: `${promptPct}%` }} /></div>
              </div>
              <div className="surface panel" style={{ "--i": 8 }}>
                <h2>Slowest steps</h2>
                <ul className="share-list">
                  {slowestSteps.map((s) => {
                    const d = formatDuration(s.duration_ms);
                    return (
                      <li key={s.step_id}>
                        <div className="share-row">
                          <span>{s.name}</span>
                          <span className="num">{d.value} {d.unit}</span>
                        </div>
                        <div className="track"><div className="fill fill-warn" style={{ width: `${(s.duration_ms / maxDur) * 100}%` }} /></div>
                      </li>
                    );
                  })}
                </ul>
              </div>
              <div className="surface panel" style={{ "--i": 9 }}>
                <h2>Failure summary</h2>
                {failedSteps.length === 0 ? (
                  <p className="empty">No failed steps in this run.</p>
                ) : (
                  <ul className="fail-list">
                    {Object.entries(failureCounts).map(([tag, n]) => (
                      <li key={tag}><span className="pill pill-tag">{tag}</span><span className="num">{n} step{n > 1 ? "s" : ""}</span></li>
                    ))}
                  </ul>
                )}
                <p className="note-small">Tags come from the offline keyword tagger.</p>
              </div>
            </aside>
            <section className="tree-col" aria-label="Trace tree">
              <h2>Trace</h2>
              <TraceTree steps={detail.tree} slowMs={SLOW_MS} totalMs={m.total_latency_ms} tags={tags} />
            </section>
          </div>
        </>
      )}
    </main>
  );
}
