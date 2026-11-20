import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Explicit cleanup so each test starts with an empty document, independent of globals.
afterEach(() => cleanup());
