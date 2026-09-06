/**
 * Vitest configuration — QuantLab frontend component/unit tests (Phase 63.0).
 *
 * Scope: fast, offline, jsdom-based tests for shared components, navigation
 * registries and pure utilities.  This is NOT a replacement for the Playwright
 * browser E2E suite (`frontend/e2e/`, real browser + running services) or for
 * the user-run production smoke pass — see
 * `docs/FRONTEND_COMPONENT_TESTING.md` for the layer boundaries.
 *
 * Deliberately minimal: one runner, one DOM environment, no Babel migration,
 * no global source transformation beyond the React plugin, and no network.
 */

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Mirrors the `@/*` path alias in tsconfig.json.
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Component/unit tests only.  Playwright specs live in e2e/ and are run by
    // `npx playwright test`; including them here would try to execute browser
    // fixtures inside jsdom.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "e2e/**"],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
    clearMocks: true,
    coverage: {
      provider: "v8",
      // Written to the gitignored artifacts tree, never committed.
      reportsDirectory: "../artifacts/frontend-coverage",
      reporter: ["text-summary"],
      include: ["src/lib/**", "src/components/**"],
    },
  },
});
