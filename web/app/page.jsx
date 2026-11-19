"use client";
import { useEffect, useState } from "react";
import TraceTree from "../components/TraceTree.jsx";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const SLOW_MS = Number(process.env.NEXT_PUBLIC_SLOW_MS) || 5000;

async function getJson(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`API returned ${res.status}`);
  return res.json();
}

export default function Page() {
  const [runs, setRuns] = useState(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson("/runs")
      .then((r) => {
        setRuns(r);
        if (r.length) setSelected(r[0].run_id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError("");
    Promise.all([
      getJson(`/runs/${encodeURIComponent(selected)}/metrics`),
      getJson(`/runs/${encodeURIComponent(selected)}/tree`),
    ])
      .then(([metrics, tree]) => setDetail({ metrics, tree }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <main>
      <h1>Agent trace lens</h1>
      {loading && <p>Loading…</p>}
      {error && <p className="error">Could not load data: {error}. Is the API running?</p>}
      {!loading && !error && runs && runs.length === 0 && (
        <p className="empty">No runs yet. Import one with <code>python -m trace_lens import file.json</code>.</p>
      )}
      {runs && runs.length > 0 && (
        <select value={selected} onChange={(e) => setSelected(e.target.value)} aria-label="Run">
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id} ({r.model})
            </option>
          ))}
        </select>
      )}
      {detail && (
        <>
          <section className="cards">
            <div>Tokens<b>{detail.metrics.total_tokens}</b></div>
            <div>Latency<b>{detail.metrics.total_latency_ms} ms</b></div>
            <div>Errors<b>{detail.metrics.error_count}</b></div>
            <div>Steps<b>{detail.metrics.step_count}</b></div>
          </section>
          <TraceTree steps={detail.tree} slowMs={SLOW_MS} />
        </>
      )}
    </main>
  );
}
