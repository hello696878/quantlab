/**
 * Scenario Studio frozen-demo regression guard (Phase 43.0).
 *
 * Frozen expectation (tag v4.60.0-public-release-candidate-demo-freeze-v1):
 * applying "Severe Cross-Asset Stress Combo" drives the composite severity to
 * 100.0/100 with 8/8 modules and the "Severe systemic stress" regime, via a
 * 200 POST to /api/scenario-studio/analyze on deterministic static sample
 * data.
 *
 * Note on "11.3 → 100.0": the 11.3 pre-stress value belongs to the Soft
 * Landing template and is part of the manual freeze evidence
 * (docs/BROWSER_SMOKE_TEST_REPORT.md); this guard asserts the deterministic
 * end state (100.0) plus the API roundtrip rather than scripting the full
 * two-template comparison. No UI values were added for this test.
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

test("severe cross-asset stress combo reaches severity 100.0 (8/8 modules)", async ({
  page,
}) => {
  const failures = trackFailedLocalRequests(page);
  await page.goto("/");
  await waitForAppSettled(page);

  await gotoView(page, "Scenario Studio", /Scenario Studio/);

  // Selecting the template triggers the debounced analyze POST; hold the
  // response promise open before clicking so the 200 cannot be missed.
  const analyzed = page.waitForResponse(
    (res) =>
      res.url().includes("/api/scenario-studio/analyze") &&
      res.status() === 200,
    { timeout: 30_000 },
  );
  await page
    .getByRole("button", { name: "Severe Cross-Asset Stress Combo" })
    .click();
  await analyzed;

  // Frozen analyzed state (all values deterministic static-sample outputs).
  await expect(page.getByText("100.0/100").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("8 / 8").first()).toBeVisible();
  await expect(
    page.getByText(/severe systemic stress/i).first(),
  ).toBeVisible();

  // Heatmap / chart area loaded.
  await expect(page.getByText(/scenario heatmap/i).first()).toBeVisible();
  expect(
    await page.locator("svg.recharts-surface").count(),
    "module impact charts rendered",
  ).toBeGreaterThanOrEqual(1);

  await expectNoVisibleNaNOrInfinity(page);
  await expectNoRawStackTrace(page);
  assertNoFailedLocalRequests(failures);
});
