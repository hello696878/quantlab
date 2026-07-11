/**
 * Frozen demo regression guard — core route walk (Phase 43.0).
 *
 * Protects the v4.60.0 public-demo path frozen at tag
 * v4.60.0-public-release-candidate-demo-freeze-v1 (evidence commit 7cf9708):
 * landing, the product-workflow pages a viewer sees, the command palette,
 * and the page-safety invariants (no NaN/Infinity, no raw stack traces,
 * no failed local API calls).
 *
 * Deliberately NOT a 37-view sweep in v1 — the full sweep stays a manual
 * runbook pass (docs/FINAL_SMOKE_TEST_RUNBOOK.md) until the harness has
 * proven stable.
 */

import { expect, test } from "@playwright/test";
import {
  assertNoFailedLocalRequests,
  expectApiOnlineIfShown,
  expectNoRawStackTrace,
  expectNoVisibleNaNOrInfinity,
  gotoView,
  maybeDismissOverlays,
  openCommandPalette,
  trackFailedLocalRequests,
  waitForAppSettled,
  type RequestFailure,
} from "./helpers";

test.describe("frozen demo route", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
  });

  test("landing page loads with the frozen hero and healthy API", async ({
    page,
  }) => {
    await expect(page.locator("header h1")).toHaveText("Home");
    await expect(
      page.getByRole("heading", { name: "QuantLab Research Terminal" }),
    ).toBeVisible();
    // Dashboard / command-center content present.
    await expect(page.getByText("Welcome to QuantLab")).toBeVisible();
    await expectApiOnlineIfShown(page);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("frozen product-workflow pages open", async ({ page }) => {
    const stops: Array<{ sidebar: string; h1: RegExp }> = [
      { sidebar: "Portfolio Showcase", h1: /QuantLab Portfolio Showcase/ },
      { sidebar: "Public Release Candidate", h1: /Public Release Candidate/ },
      { sidebar: "Demo Center", h1: /Product Demo Center/ },
      { sidebar: "Release Notes Center", h1: /Release Notes Center/ },
      { sidebar: "Developer Onboarding", h1: /Developer Onboarding/ },
    ];
    for (const stop of stops) {
      await gotoView(page, stop.sidebar);
      await expect(page.locator("header h1")).toHaveText(stop.h1);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
    }
    assertNoFailedLocalRequests(failures);
  });

  test("command palette opens with Ctrl+K and navigates", async ({ page }) => {
    await openCommandPalette(page);
    const dialog = page.getByRole("dialog", { name: "Command palette" });
    await dialog.getByRole("textbox").fill("Open Public Release Candidate");
    await page.keyboard.press("Enter");
    await expect(page.locator("header h1")).toHaveText(
      /Public Release Candidate/,
      { timeout: 10_000 },
    );
    // And once more to a lab, proving palette navigation is general.
    await openCommandPalette(page);
    await page
      .getByRole("dialog", { name: "Command palette" })
      .getByRole("textbox")
      .fill("Open Scenario Studio");
    await page.keyboard.press("Enter");
    await expect(page.locator("header h1")).toHaveText(
      /Scenario Studio/,
      { timeout: 10_000 },
    );
    await maybeDismissOverlays(page);
    assertNoFailedLocalRequests(failures);
  });

  test("saved-work empty/loaded states render without errors", async ({
    page,
  }) => {
    await gotoView(page, "Saved Reports");
    await expect(page.locator("header h1")).toHaveText(/Saved Reports/);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
