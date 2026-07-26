/**
 * Meta-Labeling Lab E2E coverage (Phase 51.0).
 *
 * Isolation policy (docs/META_LABELING_RUNBOOK.md): the only writes are the
 * idempotent demo seeds (unique demo_key; they cascade to the Model
 * Validation / Dataset Lineage / Experiment Registry idempotent demo loaders)
 * — real user records are never modified.  Threshold selection is a pure UI
 * interaction; policy saving/baselines are covered by backend tests on
 * isolated databases.  No external network.
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

const HEADER = /Meta-Labeling, Calibration & Threshold Lab/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Demo — Verified OOF sigmoid/ }),
  ).toBeVisible({ timeout: 30_000 });
}

async function expectDarkBackground(control: ReturnType<Page["getByLabel"]>): Promise<void> {
  const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
  const rgb = bg.match(/rgba?\(([^)]+)\)/);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
    expect((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255, `background ${bg} should be dark`).toBeLessThan(0.5);
    return;
  }
  const oklch = bg.match(/oklch\(\s*([\d.]+)/);
  expect(oklch, `background '${bg}' should be rgb(a) or oklch()`).not.toBeNull();
  expect(Number.parseFloat(oklch![1]), `background ${bg} should be dark`).toBeLessThan(0.5);
}

test.describe("meta-labeling lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Meta-Labeling Lab", HEADER);
  });

  test("opens with the calibration disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/never that a trade is profitable/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Uncalibrated \(overconfident/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Demo — Isotonic calibrated/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by calibration method", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Calibration", { exact: true }).selectOption("isotonic");
    await expect(page.getByRole("button", { name: /Demo — Isotonic calibrated/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Uncalibrated \(overconfident/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Uncalibrated \(overconfident/ })).toBeVisible();
  });

  test("verified OOF run: links, raw vs calibrated metrics, reliability chart", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Verified OOF sigmoid/ }).click();
    await expect(page.getByText("OOF verified").first()).toBeVisible();
    await expect(page.getByText(/Linked records/i)).toBeVisible();
    await expect(page.getByText(/Leakage-clean: yes/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in Model Validation Lab" })).toBeVisible();
    // Raw vs calibrated metrics table with ECE row.
    await expect(page.getByText("ECE", { exact: true })).toBeVisible();
    // Reliability chart + accessible bin table.
    const chart = page.locator("svg[role=img]").first();
    await expect(chart).toHaveAttribute("aria-label", /Reliability chart/);
    await expect(page.getByText(/Bin table \(accessible alternative\)/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("threshold analysis: manual selection updates coverage, no recommendation", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Verified OOF sigmoid/ }).click();
    await expect(page.locator("svg[role=img]").nth(1)).toHaveAttribute("aria-label", /Threshold analysis/);
    await page.getByText(/Threshold table \(accessible alternative\)/i).click();
    const before = await page.locator("main").innerText();
    // Click the 0.8 row in the threshold table.
    await page.locator("details table tbody tr", { hasText: /^0\.8/ }).first().click();
    await expect(async () => {
      const after = await page.locator("main").innerText();
      expect(after).not.toBe(before);
    }).toPass({ timeout: 10_000 });
    // Neutral wording: policy saving is the user's choice; nothing "optimal".
    await expect(page.getByText(/never recommends a threshold/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("optimal threshold");
    expect(body).not.toContain("recommended threshold");
    assertNoFailedLocalRequests(failures);
  });

  test("uncalibrated vs sigmoid comparison stays neutral", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("checkbox", { name: /Select Demo — Uncalibrated/ }).check();
    await page.getByRole("checkbox", { name: /Select Demo — Sigmoid \(Platt\) calibrated/ }).check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare meta-label runs")).toBeVisible();
    await expect(page.getByText("Probability metrics")).toBeVisible();
    await expect(page.getByText(/neither run is labelled better/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("failed one-class run and invalidated-dataset warning render honestly", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /One-class calibration failure/ }).click();
    await expect(page.getByText(/Execution failed:/)).toBeVisible();
    await expect(page.getByText(/both classes/i).first()).toBeVisible();
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await page.getByRole("button", { name: /Linked to an invalidated dataset/ }).click();
    await expect(page.getByText(/has been invalidated/i).first()).toBeVisible({ timeout: 15_000 });
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    for (const control of [page.getByLabel("Calibration", { exact: true }), page.getByLabel("OOF status"),
                           page.getByLabel("Status", { exact: true }), page.getByLabel("Search")]) {
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

  test("no horizontal page overflow at 1024 and 768 (list and detail)", async ({ page }) => {
    await seedDemo(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Demo — Verified OOF sigmoid/ }).click();
    await expect(page.getByText("OOF verified").first()).toBeVisible();
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
