/**
 * Overfitting Diagnostics Lab E2E coverage (Phase 53.0).
 *
 * Isolation policy (docs/OVERFITTING_DIAGNOSTICS_RUNBOOK.md): the only writes
 * are the idempotent demo seeds (unique demo_key; they cascade to the Feature
 * Diagnostics / Meta-Labeling / Model Validation / Dataset Lineage /
 * Experiment Registry idempotent demo loaders) — real user records are never
 * modified.  One deliberate exception: the invalid-baseline check clicks
 * "Mark as scope baseline" on the honestly-failed demo run's API path via the
 * UI-less 409 assertion pattern is NOT used here — the failed run simply has
 * no baseline button, which is itself asserted.  No external network.
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

const HEADER = /Backtest Overfitting, PBO & Multiple Testing Diagnostics Lab/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Demo — 14 noise candidates/ }),
  ).toBeVisible({ timeout: 60_000 });
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

test.describe("overfitting diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Overfitting Diagnostics", HEADER);
  });

  test("opens with the selection-bias disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/never proof of profitability, robustness, or safety/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /One persistent drift among noise/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Short record, constant candidate/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by metric and status", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Metric", { exact: true }).selectOption("mean_return");
    await expect(page.getByRole("button", { name: /Short record, constant candidate/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Demo — 14 noise candidates/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await page.getByLabel("Status", { exact: true }).selectOption("failed");
    await expect(page.getByRole("button", { name: /Invalid configuration/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Demo — 14 noise candidates/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Demo — 14 noise candidates/ })).toBeVisible();
  });

  test("high-PBO demo: PBO estimate, lambda distribution, zero boundary", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText("PBO — Probability of Backtest Overfitting")).toBeVisible();
    await expect(page.getByText("Estimated PBO", { exact: true })).toBeVisible();
    await expect(page.getByText(/S = 8 blocks · 70 CSCV combinations/)).toBeVisible();
    const chart = page.locator("svg[role=img]").first();
    await expect(chart).toHaveAttribute("aria-label", /Lambda distribution/);
    await expect(chart.locator("text", { hasText: "λ = 0" })).toBeVisible();
    await expect(page.getByText(/Fraction below zero \(PBO\)/)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("selection frequency and IS/OOS degradation render neutrally", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText("Candidate selection frequency (in-sample)")).toBeVisible();
    await expect(page.getByText(/Highest measured selection frequency/)).toBeVisible();
    await expect(page.getByText(/not a winner/)).toBeVisible();
    await expect(page.getByText(/CSCV splits — IS vs OOS degradation/)).toBeVisible();
    const splitRow = page.locator("tr", { hasText: "cscv-0000" }).first();
    await expect(splitRow).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const banned of ["best strategy", "winning strategy", "recommended strategy",
                          "optimal strategy", "safe strategy"]) {
      expect(body, `page must not claim "${banned}"`).not.toContain(banned);
    }
    assertNoFailedLocalRequests(failures);
  });

  test("Sharpe diagnostics: PSR, DSR, assumptions and deflation visible", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText("Sharpe diagnostics — PSR, DSR, MinTRL")).toBeVisible();
    await expect(page.getByText("Observed Sharpe", { exact: true })).toBeVisible();
    await expect(page.getByText("Kurtosis (non-excess)", { exact: true })).toBeVisible();
    await expect(page.getByText("Trials (raw)", { exact: true })).toBeVisible();
    await expect(page.getByText("E[max SR] benchmark", { exact: true })).toBeVisible();
    // The only occurrence of "probability of future profit" must be the
    // negated disclaimer; no positive "validated Sharpe" claim anywhere.
    await expect(page.getByText(/neither is the probability of future profit/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("validated sharpe");
    assertNoFailedLocalRequests(failures);
  });

  test("multiple testing: Bonferroni, Holm and BH separate with FWER/FDR explanation", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText(/Multiple-testing corrections \(alpha = 0\.05\)/)).toBeVisible();
    await expect(page.getByText(/family-wise error rate \(FWER\)/)).toBeVisible();
    await expect(page.getByText(/false discovery rate \(FDR\)/)).toBeVisible();
    await expect(page.getByText(/BH does not control FWER/)).toBeVisible();
    // noise-01 (p = 0.02): below threshold raw, above after Holm.
    const row = page.locator("tr", { hasText: "noise-01" })
      .filter({ has: page.getByText("declared", { exact: true }) }).first();
    await expect(row).toBeVisible();
    await expect(row.getByText("below threshold")).toBeVisible();
    await expect(row.getByText("above threshold").first()).toBeVisible();
    await expect(page.getByText(/never independently verified/)).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("dependence: correlated pair and approximate effective trials render", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText("Candidate dependence")).toBeVisible();
    const pairRow = page.locator("tr", { hasText: "corr-a" }).filter({ hasText: "corr-b" }).first();
    await expect(pairRow).toBeVisible();
    await expect(page.getByText("Effective trials (approx.)", { exact: true })).toBeVisible();
    await expect(page.getByText(/never treated as\s+independent/)).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("constant candidate is unavailable, one-trial DSR note, honest failure", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Short record, constant candidate/ }).click();
    await expect(page.getByText(/one effective trial — deflation is undefined/i)).toBeVisible();
    // The candidates table row (not the selection-frequency row) carries the
    // honest "unavailable" Sharpe cells for the constant candidate.
    const flatRow = page.locator("tr", { hasText: "flat-fee" })
      .filter({ has: page.getByText("unavailable", { exact: true }) }).first();
    await expect(flatRow).toBeVisible();
    await expect(page.getByText(/only 28 observations/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await page.getByRole("button", { name: /Invalid configuration/ }).click();
    await expect(page.getByText(/Execution failed:/)).toBeVisible();
    await expect(page.getByText(/no valid CSCV splits/i).first()).toBeVisible();
    // a failed run offers no baseline action at all
    await expect(page.getByRole("button", { name: "Mark as scope baseline" })).toHaveCount(0);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline: signal demo is marked; comparison stays neutral with warnings", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await page.getByRole("checkbox", { name: /Select Demo — 14 noise candidates/ }).check();
    await page.getByRole("checkbox", { name: /Select Demo — One persistent drift/ }).check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare diagnostic runs")).toBeVisible();
    await expect(page.getByText(/candidate universes differ/i)).toBeVisible();
    await expect(page.getByText(/neither run is labelled better/i)).toBeVisible();
    await expect(page.getByText(/Selection frequencies/)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("winner");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("export JSON is path- and credential-free", async ({ page }) => {
    await seedDemo(page);
    const response = await page.request.get("/api/overfitting-diagnostics/export");
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    const parsed = JSON.parse(text);
    expect(parsed.schema_version).toBe("overfitting_diagnostics_export_v1");
    for (const banned of ["C:\\\\", "/Users/", "/home/", "api_key", "apiKey",
                          "password", "secret", "pickle", "joblib"]) {
      expect(text, `export must not contain ${banned}`).not.toContain(banned);
    }
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    for (const control of [page.getByLabel("Metric", { exact: true }),
                           page.getByLabel("Status", { exact: true }),
                           page.getByLabel("Search", { exact: true })]) {
      await expectDarkBackground(control);
    }
  });

  test("table name column does not overlap the adjacent column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await seedDemo(page);
    const firstRow = page.locator("tbody tr").first();
    const nameCell = firstRow.locator("td").nth(1);
    const nextCell = firstRow.locator("td").nth(2);
    await expect(async () => {
      const nameBox = await nameCell.boundingBox();
      const nextBox = await nextCell.boundingBox();
      const btnBox = await nameCell.getByRole("button").boundingBox();
      expect(nameBox).not.toBeNull();
      expect(nextBox).not.toBeNull();
      expect(btnBox).not.toBeNull();
      expect(btnBox!.x + btnBox!.width).toBeLessThanOrEqual(nameBox!.x + nameBox!.width + 2);
      expect(nameBox!.x + nameBox!.width).toBeLessThanOrEqual(nextBox!.x + 2);
    }).toPass({ timeout: 20_000 });
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no horizontal page overflow at 1024 and 768 (list and detail)", async ({ page }) => {
    await seedDemo(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Demo — 14 noise candidates/ }).click();
    await expect(page.getByText("Estimated PBO", { exact: true })).toBeVisible();
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
