import React from "react";

export function buildTree(steps) {
  const nodes = new Map(steps.map((s) => [s.step_id, { ...s, children: [] }]));
  const roots = [];
  for (const s of steps) {
    const node = nodes.get(s.step_id);
    const parent = s.parent_id ? nodes.get(s.parent_id) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

export function formatDuration(ms) {
  if (ms >= 60000) return { value: (ms / 60000).toFixed(1), unit: "min" };
  if (ms >= 1000) return { value: (ms / 1000).toFixed(1), unit: "s" };
  return { value: String(Math.round(ms)), unit: "ms" };
}

function offsetMs(step, originMs) {
  const t = Date.parse(step.started_at);
  return Number.isFinite(t) && Number.isFinite(originMs) ? Math.max(0, t - originMs) : 0;
}

function Node({ node, slowMs, totalMs, tags, index, originMs }) {
  const failed = node.status === "error";
  const slow = node.duration_ms > slowMs;
  const cls = ["step", failed ? "failed" : "", slow ? "slow" : ""].filter(Boolean).join(" ");
  const rawPct = totalMs > 0 ? (node.duration_ms / totalMs) * 100 : 0;
  const left = totalMs > 0 ? Math.min(100, (offsetMs(node, originMs) / totalMs) * 100) : 0;
  const pct = Math.max(0, Math.min(100 - left, rawPct));
  const fill = failed ? "fill-bad" : slow ? "fill-warn" : "fill-ok";
  const d = formatDuration(node.duration_ms);
  const tag = tags && tags[node.step_id];
  return (
    <li>
      <div className={cls} data-testid={`step-${node.step_id}`} style={{ "--i": index }}>
        <div className="step-head">
          <span className={`dot ${failed ? "dot-bad" : slow ? "dot-warn" : "dot-ok"}`} aria-hidden="true" />
          <strong className="step-name">{node.name}</strong>
          <span className={`chip chip-${node.kind}`}>{node.kind}</span>
          {failed && <span className="pill pill-bad">FAILED</span>}
          {slow && <span className="pill pill-warn">SLOW</span>}
          {failed && tag && (
            <span className="pill pill-tag" data-testid={`tag-${node.step_id}`} title="Failure tag">
              {tag}
            </span>
          )}
        </div>
        <div className="meta">
          {d.value} {d.unit} · {node.tokens} tokens
        </div>
        <div className="track" role="img" aria-label={`starts at ${left.toFixed(0)}% of the run, lasts ${rawPct.toFixed(0)}% of run time`}>
          <div className={`fill ${fill}`} style={{ marginLeft: `${left}%`, width: `${pct}%` }} />
        </div>
        {failed && node.error && <pre className="err">{node.error}</pre>}
      </div>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c, i) => (
            <Node key={c.step_id} node={c} slowMs={slowMs} totalMs={totalMs} tags={tags} index={index + i + 1} originMs={originMs} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function TraceTree({ steps, slowMs = 5000, totalMs, tags }) {
  if (!steps || steps.length === 0) {
    return <p className="empty">This run has no steps.</p>;
  }
  const total = totalMs || Math.max(...steps.map((s) => s.duration_ms), 1);
  const starts = steps.map((s) => Date.parse(s.started_at)).filter(Number.isFinite);
  const originMs = starts.length ? Math.min(...starts) : NaN;
  const ticks = [0, total / 2, total].map((ms) => formatDuration(ms));
  return (
    <>
      <div className="axis" aria-hidden="true" data-testid="time-axis">
        {ticks.map((t, i) => (
          <span key={i}>{t.value === "0" ? "0" : `${t.value} ${t.unit}`}</span>
        ))}
      </div>
      <ul className="tree" role="tree">
        {buildTree(steps).map((n, i) => (
          <Node key={n.step_id} node={n} slowMs={slowMs} totalMs={total} tags={tags} index={i} originMs={originMs} />
        ))}
      </ul>
    </>
  );
}
