import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TraceTree, { formatDuration } from "../components/TraceTree.jsx";

const steps = [
  { step_id: "a", parent_id: null, name: "root", kind: "agent", status: "ok", error: null, duration_ms: 9000, tokens: 0 },
  { step_id: "b", parent_id: "a", name: "think", kind: "llm", status: "ok", error: null, duration_ms: 1000, tokens: 50 },
  { step_id: "c", parent_id: "a", name: "search", kind: "tool", status: "error", error: "boom", duration_ms: 2000, tokens: 0 },
  { step_id: "d", parent_id: "c", name: "retry", kind: "tool", status: "ok", error: null, duration_ms: 6000, tokens: 0 },
];

describe("TraceTree", () => {
  it("renders all nodes in nesting order", () => {
    render(<TraceTree steps={steps} slowMs={5000} />);
    const ids = screen.getAllByTestId(/^step-/).map((el) => el.dataset.testid);
    expect(ids).toEqual(["step-a", "step-b", "step-c", "step-d"]);
    const child = screen.getByTestId("step-d");
    expect(screen.getByTestId("step-c").parentElement.querySelector("ul").contains(child)).toBe(true);
  });

  it("flags failed and slow steps only where applicable", () => {
    render(<TraceTree steps={steps} slowMs={5000} />);
    expect(screen.getByTestId("step-c").className).toContain("failed");
    expect(screen.getByTestId("step-c").className).not.toContain("slow");
    expect(screen.getByTestId("step-a").className).toContain("slow");
    expect(screen.getByTestId("step-d").className).toContain("slow");
    expect(screen.getByTestId("step-b").className).not.toMatch(/slow|failed/);
  });

  it("respects a configurable threshold", () => {
    render(<TraceTree steps={steps} slowMs={500} />);
    expect(screen.getByTestId("step-b").className).toContain("slow");
  });

  it("shows a failure tag badge only on failed steps", () => {
    render(<TraceTree steps={steps} slowMs={5000} tags={{ c: "tool_error", b: "timeout" }} />);
    expect(screen.getByTestId("tag-c").textContent).toBe("tool_error");
    expect(screen.queryByTestId("tag-b")).toBeNull();
  });

  it("formats durations with units", () => {
    expect(formatDuration(10000)).toEqual({ value: "10.0", unit: "s" });
    expect(formatDuration(850)).toEqual({ value: "850", unit: "ms" });
  });

  it("shows an empty state", () => {
    render(<TraceTree steps={[]} />);
    expect(screen.getByText("This run has no steps.")).toBeTruthy();
  });
});
