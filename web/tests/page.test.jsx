import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Page from "../app/page.jsx";

const RUN = { run_id: "run-001", model: "llama3.2", task: "t", started_at: "2025-01-01T00:00:00Z" };
const METRICS = {
  total_tokens: 450, prompt_tokens: 320, completion_tokens: 130, total_latency_ms: 9000,
  step_latency_sum_ms: 12000, error_count: 1, step_count: 2,
  steps: [
    { step_id: "a", name: "root", tokens: 0, duration_ms: 9000 },
    { step_id: "b", name: "search", tokens: 450, duration_ms: 3000 },
  ],
};
const TREE = [
  { step_id: "a", parent_id: null, name: "root", kind: "agent", status: "ok", error: null, duration_ms: 9000, tokens: 0 },
  { step_id: "b", parent_id: "a", name: "search", kind: "tool", status: "error", error: "boom", duration_ms: 3000, tokens: 450 },
];

function json(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
}

function route(url) {
  if (url.endsWith("/runs")) return json([RUN]);
  if (url.endsWith("/metrics")) return json(METRICS);
  if (url.endsWith("/tree")) return json(TREE);
  if (url.includes("/tags")) return json([{ step_id: "b", tag: "tool_error", method: url.includes("llm") ? "llm" : "keyword" }]);
  return json({}, 404);
}

function setSearch(search) {
  window.history.pushState({}, "", `/${search}`);
}

beforeEach(() => setSearch(""));
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Page states", () => {
  it("shows the loading skeleton while the request is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<Page />);
    expect(screen.getByText("Loading traces…")).toBeTruthy();
    expect(screen.queryByText("No traces in this run")).toBeNull();
  });

  it("shows the empty state when there are no runs", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json([])));
    render(<Page />);
    expect(await screen.findByText("No traces in this run")).toBeTruthy();
    expect(screen.getByText(/python -m trace_lens import/)).toBeTruthy();
    expect(screen.getByLabelText("Run").disabled).toBe(true);
    expect(screen.queryByText("Loading traces…")).toBeNull();
  });

  it("shows the error state and Retry re-fetches", async () => {
    let fail = true;
    const fetchMock = vi.fn((url) => (fail ? json({}, 500) : route(url)));
    vi.stubGlobal("fetch", fetchMock);
    render(<Page />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not read traces");
    expect(alert.textContent).toContain("API returned 500");
    const callsBefore = fetchMock.mock.calls.length;

    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBefore));
    expect(await screen.findByText("Failure summary")).toBeTruthy();
    expect(screen.queryByText("Could not read traces")).toBeNull();
  });

  it("previews states via ?state=", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    setSearch("?state=empty");
    const { unmount } = render(<Page />);
    expect(await screen.findByText("No traces in this run")).toBeTruthy();
    unmount();
    setSearch("?state=error");
    render(<Page />);
    expect((await screen.findByRole("alert")).textContent).toContain("API returned 500");
  });
});

describe("Tagging method toggle", () => {
  it("requests keyword tags first and LLM tags after toggling", async () => {
    const fetchMock = vi.fn((url) => route(url));
    vi.stubGlobal("fetch", fetchMock);
    render(<Page />);
    expect(await screen.findByTestId("tag-b")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([u]) => u.includes("/tags?method=keyword"))).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /LLM/ }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u.includes("/tags?method=llm"))).toBe(true));
  });

  it("explains when the LLM tagger is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => (url.includes("method=llm") ? json({}, 502) : route(url))));
    render(<Page />);
    await screen.findByTestId("tag-b");
    fireEvent.click(screen.getByRole("button", { name: /LLM/ }));
    expect(await screen.findByText(/LLM tagger unavailable/)).toBeTruthy();
  });
});
