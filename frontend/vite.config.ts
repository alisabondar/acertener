import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, lazyPlugins } from "vite-plus";

// https://vite.dev/config/
export default defineConfig({
  // Written by the backend's export script; left exactly as exported.
  fmt: {
    ignorePatterns: [
      "src/api/openapi.json",
      "src/test/role-permissions.json",
      "test-results/**",
      "playwright-report/**",
      "coverage/**",
    ],
  },
  lint: {
    plugins: ["react", "typescript", "oxc"],
    ignorePatterns: ["src/api/schema.d.ts"],
    rules: {
      "react/rules-of-hooks": "error",
      "react/only-export-components": [
        "warn",
        {
          allowConstantExport: true,
        },
      ],
      "vite-plus/prefer-vite-plus-imports": "error",
    },
    // shadcn's generated components export variants beside components; we don't edit them.
    overrides: [
      {
        files: ["src/components/ui/**", "src/hooks/use-mobile.ts"],
        rules: { "react/only-export-components": "off", "react/set-state-in-effect": "off" },
      },
    ],
    options: {
      typeAware: true,
      typeCheck: true,
    },
    jsPlugins: [
      {
        name: "vite-plus",
        specifier: "vite-plus/oxlint-plugin",
      },
    ],
  },
  plugins: lazyPlugins(() => [react(), tailwindcss()]),
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // In development the browser calls /api on its own origin; Vite forwards it to FastAPI
  // (at api:8000 inside Docker Compose).
  server: { proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright runs the end-to-end specs against the real stack, not Vitest.
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // Generated code, vendored shadcn primitives and test helpers aren't ours to cover.
      exclude: ["src/api/schema.d.ts", "src/components/ui/**", "src/test/**", "src/**/*.test.*"],
      // A little under today's numbers, so CI catches a drop without failing on noise.
      thresholds: { statements: 88, branches: 78, functions: 84, lines: 88 },
    },
  },
});
