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
    <div role="status" aria-busy="true">
      <span className="sr-only">Loading traces…</span>
      <div className="kpis" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`surface skeleton sk-kpi${i === 0 ? " kpi-hero" : ""}`}>
            <span className="sk-line sk-short" />
            <span className="sk-line sk-big" />
            <span className="sk-line sk-bar" />
          </div>
        ))}
      </div>
      <div aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="surface skeleton sk-row" style={{ marginLeft: i === 0 ? 0 : `${i * 0.8}rem` }}>
            <span className="sk-line sk-med" />
            <span className="sk-line sk-bar" />
          </div>
        ))}
      </div>
    </div>
  );
}

function CopyCommand({ command }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    const done = () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(command).then(done, () => {});
    }
  };
  return (
    <div className="cmd">
      <code>{command}</code>
      <button type="button" className="btn btn-cta" onClick={copy} aria-label={`Copy command: ${command}`}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function EmptyIllustration() {
  return (
    <svg className="illus" viewBox="0 0 120 80" width="120" height="80" aria-hidden="true">
      <rect x="4" y="6" width="112" height="68" rx="14" fill="#0a0d16" stroke="#485b73" strokeOpacity="0.5" />
      <rect x="18" y="20" width="44" height="7" rx="3.5" fill="#485b73" opacity="0.6" />
      <rect x="18" y="34" width="84" height="7" rx="3.5" fill="#485b73" opacity="0.35" />
      <rect x="30" y="48" width="60" height="7" rx="3.5" fill="#485b73" opacity="0.35" />
      <path d="M18 64h20l6-8 8 14 6-6h44" fill="none" stroke="#7ee0b5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const KINDS = ["agent", "llm", "tool"];

const METHODS = [
  { id: "keyword", label: "Keyword", hint: "offline rules" },
  { id: "llm", label: "LLM", hint: "local Ollama" },
];

export default function Page() {
  const [runs, setRuns] = useState(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);
  const [tags, setTags] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [method, setMethod] = useState("keyword");
  const [tagsLoading, setTagsLoading] = useState(false);
  const [tagError, setTagError] = useState("");
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
  }, [selected, attempt]);

  useEffect(() => {
    if (!selected) return;
    let live = true;
    setTagsLoading(true);
    setTagError("");
    getJson(`/runs/${encodeURIComponent(selected)}/tags?method=${method}`)
      .then((list) => live && setTags(Object.fromEntries(list.map((t) => [t.step_id, t.tag]))))
      .catch((e) => {
        if (!live) return;
        setTags({});
        setTagError(method === "llm" ? "LLM tagger unavailable (is Ollama running?). No tags shown." : e.message);
      })
      .finally(() => live && setTagsLoading(false));
    return () => {
      live = false;
    };
  }, [selected, attempt, method]);

  const m = detail && detail.metrics;
  const lat = m ? formatDuration(m.total_latency_ms) : null;
  const totalTokens = m ? m.total_tokens : 0;
  const promptPct = totalTokens ? (m.prompt_tokens / totalTokens) * 100 : 0;
  const topSteps = m ? [...m.steps].sort((a, b) => b.tokens - a.tokens).filter((s) => s.tokens > 0) : [];
  const slowestSteps = m ? [...m.steps].sort((a, b) => b.duration_ms - a.duration_ms).slice(0, 4) : [];
  const maxDur = slowestSteps.length ? Math.max(slowestSteps[0].duration_ms, 1) : 1;
  const failedSteps = detail ? detail.tree.filter((s) => s.status === "error") : [];
  const kindCounts = { agent: 0, llm: 0, tool: 0 };
  if (detail) detail.tree.forEach((s) => { if (s.kind in kindCounts) kindCounts[s.kind] += 1; });
  const kindTotal = Math.max(1, kindCounts.agent + kindCounts.llm + kindCounts.tool);
  const kindNote = KINDS.map((k) => `${kindCounts[k]} ${k}`).join(" · ");
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

      <div className="states" aria-live="polite">
        {error && (
          <div className="panel panel-bad" role="alert">
            <svg className="icon" viewBox="0 0 24 24" width="36" height="36" aria-hidden="true">
              <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M12 7v6M12 16.5v.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <strong>Could not read traces</strong>
            <p>{error}. Is the API running at {API}, and is <code>TRACE_DB_PATH</code> pointing at a readable <code>traces.db</code>?</p>
            <button type="button" className="btn" onClick={retry}>Retry</button>
          </div>
        )}

        {loading && !error && <Skeleton />}

        {!loading && !error && runs && runs.length === 0 && (
          <div className="surface panel empty" role="status" style={{ "--i": 1 }}>
            <EmptyIllustration />
            <strong>No traces in this run</strong>
            <p>Point <code>TRACE_DB_PATH</code> at your <code>traces.db</code>, or import a trace:</p>
            <CopyCommand command="python -m trace_lens import examples/sample_trace.json" />
          </div>
        )}
      </div>

      {runs && (
        <div className="picker" style={{ "--i": 1 }}>
          <label htmlFor="run-select" className="label">Run</label>
          <div className="select-wrap">
            <select id="run-select" value={selected} disabled={runs.length === 0}
              onChange={(e) => setSelected(e.target.value)}>
              {runs.length === 0 && <option value="">No runs available</option>}
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
              note={`${formatDuration(m.step_latency_sum_ms).value} ${formatDuration(m.step_latency_sum_ms).unit} step sum`}>
              <div className="track thin"
                title="Wall-clock run time as a share of the summed step time (nested steps overlap, so the sum can be larger)">

                <div className="fill fill-warn"
                  style={{ width: `${m.step_latency_sum_ms ? Math.min(100, (m.total_latency_ms / m.step_latency_sum_ms) * 100) : 0}%` }} />
              </div>
            </Kpi>
            <Kpi label="Errors" value={m.error_count} bad={m.error_count > 0} index={4}
              note={`${m.step_count ? Math.round((m.error_count / m.step_count) * 100) : 0}% failed`}>
              <div className="track thin">
                <div className="fill fill-bad" style={{ width: `${m.step_count ? (m.error_count / m.step_count) * 100 : 0}%` }} />
              </div>
            </Kpi>
            <Kpi label="Steps" value={m.step_count} index={5} note={kindNote}>
              <div className="track thin stack" role="img" aria-label={kindNote}>
                {KINDS.map((k) => kindCounts[k] > 0 && (
                  <div key={k} className={`seg-fill seg-${k}`} style={{ width: `${(kindCounts[k] / kindTotal) * 100}%` }} />
                ))}
              </div>
            </Kpi>
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
                <div className="seg" role="group" aria-label="Tagging method">
                  {METHODS.map((o) => (
                    <button key={o.id} type="button" className={`seg-btn${method === o.id ? " on" : ""}`}
                      aria-pressed={method === o.id} onClick={() => setMethod(o.id)}>
                      {o.label}<small>{o.hint}</small>
                    </button>
                  ))}
                </div>
                {tagsLoading && <p className="note-small" role="status">Tagging…</p>}
                {tagError && <p className="note-small note-bad" role="alert">{tagError}</p>}
                <p className="note-small">
                  {method === "llm"
                    ? "Tags come from a local Ollama model (at most 10 distinct errors per request)."
                    : "Tags come from the offline keyword rules."}
                </p>
              </div>
            </aside>
            <section className="tree-col" aria-label="Trace tree">
              <h2>Trace</h2>
              <TraceTree steps={detail.tree} slowMs={SLOW_MS} totalMs={m.total_latency_ms} tags={tags} />
              <ul className="legend" aria-label="Legend">
                <li><span className="dot dot-ok" aria-hidden="true" /> ok</li>
                <li><span className="dot dot-warn" aria-hidden="true" /> slower than {formatDuration(SLOW_MS).value} {formatDuration(SLOW_MS).unit}</li>
                <li><span className="dot dot-bad" aria-hidden="true" /> failed</li>
                <li className="legend-sum">{m.step_count} steps · {lat.value} {lat.unit} wall time</li>
              </ul>
            </section>
          </div>
        </>
      )}
    </main>
  );
}
