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

function Node({ node, slowMs }) {
  const failed = node.status === "error";
  const slow = node.duration_ms > slowMs;
  const cls = ["step", failed ? "failed" : "", slow ? "slow" : ""].filter(Boolean).join(" ");
  return (
    <li>
      <div className={cls} data-testid={`step-${node.step_id}`}>
        <strong>{node.name}</strong> <span className="kind">{node.kind}</span>
        <span className="meta">
          {node.duration_ms} ms · {node.tokens} tokens
        </span>
        {failed && <span className="badge">FAILED</span>}
        {slow && <span className="badge">SLOW</span>}
        {failed && node.error && <div className="err">{node.error}</div>}
      </div>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <Node key={c.step_id} node={c} slowMs={slowMs} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function TraceTree({ steps, slowMs = 5000 }) {
  if (!steps || steps.length === 0) {
    return <p className="empty">This run has no steps.</p>;
  }
  return (
    <ul className="tree" role="tree">
      {buildTree(steps).map((n) => (
        <Node key={n.step_id} node={n} slowMs={slowMs} />
      ))}
    </ul>
  );
}
