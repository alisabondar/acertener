import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real stack: the API in demo mode with seeded data, and the app.
 * Start both first (see the README), or set E2E_BASE_URL to point somewhere else.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  // Personas share one seeded database, so specs run one at a time in a fixed order.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
