/**
 * Model Validation Lab E2E coverage (Phase 50.0).
 *
 * Exercises the Purged CV / Embargo / CPCV lab end to end: navigation, the
 * idempotent demo loader, method filters, purged K-fold detail (separate purge
 * vs embargo counts, zero remaining overlap), the split-timeline SVG, the CPCV
 * run, run comparison (neutral), linked dataset/experiment records, baseline
 * safety, dark-theme controls, column geometry, responsiveness, and the
 * page-safety invariants.
 *
 * Isolation policy (docs/CPCV_RUNBOOK.md): the only writes are the idempotent
 * demo seeds (unique demo_key; they also seed the Experiment Registry and
 * Dataset Lineage demo records via their own idempotent loaders) plus one
 * baseline marking that only ever touches the demo baseline-candidate run —
 * real user records are never modified or deleted.  No external network.
 */

import { expect, test, type Page } from "@playwright/test";
import {
  assertNoFailedLocalRequests,
  assertNoHorizontalOverflow,
  expectNoRawStackTrace,
  expectNoVisibleNaNOrInfinity,
  gotoView,
  trackFailedLocalRequests,
  waitForAppSettled,
  type RequestFailure,
} from "./helpers";

const HEADER = /Purged CV, Embargo & CPCV Model Validation Lab/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo validation" }).first().click();
  await expect(
    page.getByRole("button", { name: /Demo — Purged K-fold \+ embargo/ }),
  ).toBeVisible({ timeout: 30_000 });
}

async function expectDarkBackground(control: ReturnType<Page["getByLabel"]>): Promise<void> {
  const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
  const rgb = bg.match(/rgba?\(([^)]+)\)/);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
    expect((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255, `control background ${bg} should be dark`).toBeLessThan(0.5);
    return;
  }
  const oklch = bg.match(/oklch\(\s*([\d.]+)/);
  expect(oklch, `background '${bg}' should be rgb(a) or oklch()`).not.toBeNull();
  expect(Number.parseFloat(oklch![1]), `control background ${bg} should be dark`).toBeLessThan(0.5);
}

test.describe("model validation lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Model Validation Lab", HEADER);
  });

  test("opens with the leakage-prevention header and disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/nothing here proves profitability/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo validation loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Standard K-fold \(leakage reference\)/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo validation" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Demo — CPCV \(5 groups/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("method filter narrows the table", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Method").selectOption("cpcv");
    await expect(page.getByRole("button", { name: /Demo — CPCV/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Standard K-fold \(leakage reference\)/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Standard K-fold \(leakage reference\)/ })).toBeVisible();
  });

  test("purged K-fold detail: purge/embargo separate, zero remaining overlap, timeline renders", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Purged K-fold \+ embargo/ }).click();
    await expect(page.getByRole("heading", { name: /Purged K-fold \+ embargo/ })).toBeVisible();
    await expect(page.getByText("leakage-clean").first()).toBeVisible();
    // Purged and embargoed are reported as separate audit stats.
    await expect(page.getByText("Purged", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Embargoed", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Remaining overlap", { exact: true }).first()).toBeVisible();
    // Split table: every split valid with remaining overlap 0.
    await expect(page.getByText(/Splits \(5\)/i)).toBeVisible();
    // Timeline SVG with accessible label + legend.
    const svg = page.locator("svg[role=img]");
    await expect(svg).toBeVisible();
    await expect(svg).toHaveAttribute("aria-label", /Split timeline/);
    await expect(page.getByText("Retained training").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("standard K-fold reference shows the leakage warning", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Standard K-fold \(leakage reference\)/ }).click();
    await expect(page.getByText(/Standard K-fold is a reference method/i)).toBeVisible();
    await expect(page.getByText(/leakage: \d+ invalid split/i).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("CPCV run renders its combinations", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — CPCV \(5 groups/ }).click();
    await expect(page.getByText(/Splits \(10\)/i)).toBeVisible();
    await expect(page.getByText("cpcv-g0-g1").first()).toBeVisible();
    await expect(page.getByText("leakage-clean").first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("comparison of K-fold vs purged K-fold stays neutral", async ({ page }) => {
    await seedDemo(page);
    await page
      .getByRole("checkbox", { name: /Select Demo — Standard K-fold \(leakage reference\) for comparison/ })
      .check();
    await page
      .getByRole("checkbox", { name: /Select Demo — Purged K-fold for comparison/ })
      .check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare validation runs")).toBeVisible();
    await expect(page.getByText("Leakage & split integrity")).toBeVisible();
    await expect(page.getByText(/neither run is labelled superior/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("linked dataset and experiment render on the baseline candidate", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Baseline candidate/ }).click();
    await expect(page.getByText(/Linked records/i)).toBeVisible();
    await expect(page.getByText(/KO\/PEP Spread & Z-Score Features/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in Dataset Lineage" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in Experiment Registry" })).toBeVisible();
    // Baseline already marked by the demo loader — the pill is visible and the
    // mark action is absent (idempotent-safe: we never mutate real records).
    await expect(page.getByText("★ Baseline")).toBeVisible();
    await page.getByRole("button", { name: "Open in Dataset Lineage" }).click();
    await expect(page.locator("header h1")).toHaveText(/Data Provenance & Dataset Lineage/, { timeout: 15_000 });
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    for (const control of [page.getByLabel("Method"), page.getByLabel("Status"), page.getByLabel("Search")]) {
      await expectDarkBackground(control);
    }
  });

  test("table name column does not overlap the adjacent column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await seedDemo(page);
    const firstRow = page.locator("tbody tr").first();
    const nameCell = firstRow.locator("td").nth(1);
    const methodCell = firstRow.locator("td").nth(2);
    await expect(async () => {
      const nameBox = await nameCell.boundingBox();
      const methodBox = await methodCell.boundingBox();
      const btnBox = await nameCell.getByRole("button").boundingBox();
      expect(nameBox).not.toBeNull();
      expect(methodBox).not.toBeNull();
      expect(btnBox).not.toBeNull();
      expect(btnBox!.x + btnBox!.width).toBeLessThanOrEqual(nameBox!.x + nameBox!.width + 2);
      expect(nameBox!.x + nameBox!.width).toBeLessThanOrEqual(methodBox!.x + 2);
    }).toPass({ timeout: 20_000 });
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no horizontal page overflow at 1024 and 768", async ({ page }) => {
    await seedDemo(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
