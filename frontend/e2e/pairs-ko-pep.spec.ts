/**
 * KO/PEP Pairs Trading fixture regression guard (Phase 43.0).
 *
 * Frozen expectation (tag v4.60.0-public-release-candidate-demo-freeze-v1,
 * evidence: docs/screenshots/release_pairs_backtest.png): the deterministic
 * KO/PEP pairs demo over 2016-07-11 → 2026-07-11 produces 119 trade events,
 * strategy Total Return -23.0% vs Buy & Hold +112.7%, with 4 charts and a
 * paginated trade log — served entirely by the network-free sample fixture
 * (`app/data.py::sample_pairs_close`; the backend checks `is_demo_pair`
 * BEFORE any fetch, so no live provider is ever touched for KO/PEP).
 *
 * Determinism note: the app's default date range is relative to "today", so
 * this guard explicitly pins the FROZEN date range. The frozen metrics
 * belong to that range; letting the dates float would change the sample
 * series and produce different (still deterministic, but different) numbers.
 * No quant logic is altered by this test.
 */

import { expect, test } from "@playwright/test";
import {
  assertNoFailedLocalRequests,
  expectNoRawStackTrace,
  expectNoVisibleNaNOrInfinity,
  gotoView,
  trackFailedLocalRequests,
  waitForAppSettled,
} from "./helpers";

const FROZEN_START = "2016-07-11";
const FROZEN_END = "2026-07-11";

test("KO/PEP pairs fixture reproduces the frozen 119-trade result", async ({
  page,
}) => {
  const failures = trackFailedLocalRequests(page);
  await page.goto("/");
  await waitForAppSettled(page);

  await gotoView(page, "Backtest");
  await expect(page.locator("header h1")).toHaveText(/Backtest/);

  // Select the Pairs Trading strategy card (its label starts with the name).
  await page
    .getByRole("button", { name: /^Pairs Trading/ })
    .first()
    .click();
  await page.waitForTimeout(600);

  // The demo pair must already be the default — the frozen demo relies on it.
  const tickers = page.locator('input[type="text"]');
  await expect(tickers.nth(0)).toHaveValue("KO");
  await expect(tickers.nth(1)).toHaveValue("PEP");

  // Pin the frozen date range (defaults are relative to today — see header).
  const dates = page.locator('input[type="date"]');
  await dates.nth(0).fill(FROZEN_START);
  await dates.nth(1).fill(FROZEN_END);

  const done = page.waitForResponse(
    (res) => res.url().includes("/api/backtest/pairs") && res.status() === 200,
    { timeout: 90_000 },
  );
  await page.getByRole("button", { name: "Run Backtest", exact: true }).click();
  await done;

  // Frozen metrics (fixture-deterministic for the pinned range).
  await expect(page.getByText(/Showing 1.20 of 119 trades/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("-23.0%").first()).toBeVisible();
  await expect(page.getByText("+112.7%").first()).toBeVisible();

  // Charts + trade log loaded.
  expect(
    await page.locator("svg.recharts-surface").count(),
    "result charts rendered",
  ).toBeGreaterThanOrEqual(4);
  await expect(page.getByText(/LONG SPREAD/).first()).toBeVisible();

  await expectNoVisibleNaNOrInfinity(page);
  await expectNoRawStackTrace(page);
  // No live provider: every request must be local and successful.
  assertNoFailedLocalRequests(failures);
});
