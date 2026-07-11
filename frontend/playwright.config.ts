/**
 * QuantLab browser E2E harness — Playwright config (Phase 43.0).
 *
 * Conservative by design:
 *  - Tests target an ALREADY-RUNNING local frontend (dev :3000 or prod :3100).
 *    This config never starts servers (no `webServer` block, no npm run
 *    dev/build) — start them yourself first (see docs/BROWSER_E2E_RUNBOOK.md).
 *  - One browser project. By default it drives the OS-installed Microsoft
 *    Edge (`channel: "msedge"`) so no browser download is required on the
 *    reference Windows setup; set E2E_BROWSER_CHANNEL=chrome, or install
 *    Playwright's own Chromium (`npx playwright install chromium`) and set
 *    E2E_BROWSER_CHANNEL= (empty) to use it.
 *  - All generated evidence goes under ../artifacts/e2e/** (gitignored via
 *    the repo-root `artifacts/` rule). The frozen release evidence under
 *    docs/screenshots/release_*.png is never written by this harness.
 *  - No external network, no live providers, no auth, no telemetry.
 *
 * E2E green is a regression signal for the frozen demo path only — not a
 * production, trading, or compliance certification.
 */

import { defineConfig } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

// "msedge" (default) / "chrome" use OS-installed browsers; set to "" after
// `npx playwright install chromium` to use Playwright's bundled Chromium.
const channel = process.env.E2E_BROWSER_CHANNEL ?? "msedge";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../artifacts/e2e/test-results",
  fullyParallel: false, // deterministic order; the pairs run is backend-heavy
  workers: 1,
  retries: 0, // a frozen-demo regression must fail loudly, not retry away
  timeout: 120_000, // the KO/PEP pairs backtest takes ~10s on the backend
  reporter: [
    ["list"],
    ["html", { outputFolder: "../artifacts/e2e/playwright-report", open: "never" }],
  ],
  use: {
    baseURL,
    ...(channel ? { channel } : {}),
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Video is deliberately OFF in v1: it requires Playwright's downloadable
    // ffmpeg component, and the zero-download harness (OS Edge channel) is
    // the point. Traces + failure screenshots are the evidence. To enable:
    // `npx playwright install ffmpeg`, then set video: "retain-on-failure".
    video: "off",
  },
  projects: [{ name: "chromium" }],
});
