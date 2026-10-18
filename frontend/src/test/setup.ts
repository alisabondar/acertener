import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, vi } from "vite-plus/test";

import { personaStore } from "@/api/persona";

import { server } from "./msw/server";

// jsdom has no matchMedia; report a desktop-width screen so layouts render their desktop form.
vi.stubGlobal("matchMedia", (query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
}));

// Started on load, before test files import the API client, so it captures the mocked fetch.
// Any request without a handler fails the test, so no test silently hits a real network.
server.listen({ onUnhandledFrame: "error" });
afterEach(() => {
  server.resetHandlers();
  personaStore.set(null);
  cleanup();
});
afterAll(() => server.close());
