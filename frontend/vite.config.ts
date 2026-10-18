import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, lazyPlugins } from "vite-plus";

// https://vite.dev/config/
export default defineConfig({
  // The backend writes openapi.json; CI diffs it byte-for-byte, so the formatter leaves it alone.
  fmt: { ignorePatterns: ["src/api/openapi.json"] },
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
  // In development the browser calls /api on its own origin; Vite forwards it to FastAPI.
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
