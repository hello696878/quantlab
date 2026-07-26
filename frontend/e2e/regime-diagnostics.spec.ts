/**
 * Regime Diagnostics Lab E2E coverage (Phase 54.0).
 *
 * Isolation policy (docs/REGIME_DIAGNOSTICS_RUNBOOK.md): the only writes are
 * the idempotent demo seeds (unique demo_key; they cascade through every
 * other registry's idempotent demo loader) — real user records are never
 * modified.  No external network.
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

const HEADER = /Market Regime Robustness & Conditional Performance Lab/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Volatility \+ trend \+ combined regimes/ }),
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

test.describe("regime diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Regime Diagnostics", HEADER);
  });

  test("opens with the no-look-ahead disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/no-look-ahead policy/i).first()).toBeVisible();
    await expect(page.getByText(/regimes are never predictions/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Rank reversal across trend regimes/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Training-only verified thresholds/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by integrity status", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Integrity", { exact: true }).selectOption("verified_from_validation_split");
    await expect(page.getByRole("button", { name: /Training-only verified thresholds/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Full-sample descriptive/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Full-sample descriptive/ })).toBeVisible();
  });

  test("training-verified run: integrity, lag policy and thresholds visible", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Training-only verified thresholds/ }).click();
    await expect(page.getByText("Verified (training split)").first()).toBeVisible();
    await expect(page.getByText(/Regime definitions \(1\)/)).toBeVisible();
    const defRow = page.locator("tr", { hasText: "vol-train" }).first();
    await expect(defRow).toBeVisible();
    await expect(defRow.getByText("training_quantile")).toBeVisible();
    // lookback and lag are explicit columns; the no-look-ahead note is printed
    await expect(page.getByText(/never sees its own period/)).toBeVisible();
    await expect(page.getByText(/Open in Model Validation Lab/)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("full-sample descriptive run is warned and never called verified", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Full-sample descriptive \+ drawdown state/ }).click();
    await expect(page.getByText("Full-sample descriptive").first()).toBeVisible();
    await expect(page.getByText(/not leakage-safe/i).first()).toBeVisible();
    // the drawdown definition stays verified-causal (trailing peak only)
    const ddRow = page.locator("tr", { hasText: "dd-state" }).first();
    await expect(ddRow.getByText("Verified causal rule")).toBeVisible();
    const volRow = page.locator("tr", { hasText: "vol-full" }).first();
    await expect(volRow.getByText("Full-sample descriptive")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("coverage, conditional metrics and rare-regime withholding render", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Rank reversal across trend regimes/ }).click();
    await expect(page.getByText("Coverage", { exact: true })).toBeVisible();
    await expect(page.getByText("(unassigned)").first()).toBeVisible();
    await expect(page.getByText(/Conditional performance \(candidate × regime\)/)).toBeVisible();
    await expect(page.getByText(/a statistic never outranks its sample size/i)).toBeVisible();
    // the rare neutral regime is honestly withheld
    await expect(page.getByText("low sample").first()).toBeVisible();
    await expect(page.getByText("unavailable").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("rank reversal is visible in the rank-stability matrix", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Rank reversal across trend regimes/ }).click();
    await expect(page.getByText("Rank stability across regimes")).toBeVisible();
    await expect(page.getByText(/rank 1 = lowest measured regime mean/)).toBeVisible();
    const bullRow = page.locator("tr", { hasText: "bull-rider" }).last();
    await expect(bullRow).toBeVisible();
    await expect(page.getByText(/no winner is identified/i)).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("concentration and robustness classifications render neutrally", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Volatility \+ trend \+ combined regimes/ }).click();
    await expect(page.getByText("Robustness across regimes")).toBeVisible();
    await expect(page.getByText("concentrated").first()).toBeVisible();
    await expect(page.getByText(/never robustness proof/i)).toBeVisible();
    await expect(page.getByText("Concentration", { exact: true })).toBeVisible();
    await expect(page.getByText(/never proof of\s+overfitting/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const banned of ["best regime", "best strategy", "recommended strategy",
                          "profitable regime", "regime prediction"]) {
      expect(body, `page must not claim "${banned}"`).not.toContain(banned);
    }
    assertNoFailedLocalRequests(failures);
  });

  test("regime timeline and transitions render with combined regime", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Volatility \+ trend \+ combined regimes/ }).click();
    await expect(page.getByText("Regime timeline (effective labels)")).toBeVisible();
    const strips = page.locator("svg[role=img]");
    await expect(strips.first()).toHaveAttribute("aria-label", /Effective .* regime labels/);
    expect(await strips.count()).toBeGreaterThanOrEqual(3);
    // combined labels like "low|upward" appear
    await expect(page.getByText(/low\|upward/).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Regime transitions" })).toBeVisible();
    await expect(page.getByText(/never causal claims/i)).toBeVisible();
    await expect(page.locator("tr", { hasText: "→" }).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("invalid future-looking definition shows an honest invalid state", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Invalid future-looking definition/ }).click();
    const badRow = page.locator("tr", { hasText: "future-labels" }).first();
    await expect(badRow.getByText("Invalid")).toBeVisible();
    await expect(page.getByText(/centered \(future-looking\) construction/i).first()).toBeVisible();
    // the valid causal definition coexists
    const okRow = page.locator("tr", { hasText: "vol-ok" }).first();
    await expect(okRow.getByText("Verified causal rule")).toBeVisible();
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline is marked on the verified run; invalid-definition run rejected", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await page.getByRole("button", { name: /Invalid future-looking definition/ }).click();
    await page.getByRole("button", { name: "Mark as scope baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/no invalid definitions/i)).toBeVisible();
    // The 409 from mark-baseline is the expected outcome under test.
    const unexpected = failures.filter(
      (f) => !(f.url.includes("/mark-baseline") && f.detail === "HTTP 409"),
    );
    expect(unexpected, `unexpected failed requests: ${JSON.stringify(unexpected)}`).toEqual([]);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("checkbox", { name: /Select Demo — Volatility \+ trend/ }).check();
    await page.getByRole("checkbox", { name: /Select Demo — Rank reversal/ }).check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare regime-diagnostic runs")).toBeVisible();
    await expect(page.getByText(/universes differ/i)).toBeVisible();
    await expect(page.getByText(/neither run is labelled better/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("winner");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("export JSON is path- and credential-free", async ({ page }) => {
    await seedDemo(page);
    const response = await page.request.get("/api/regime-diagnostics/export");
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    const parsed = JSON.parse(text);
    expect(parsed.schema_version).toBe("regime_diagnostics_export_v1");
    for (const banned of ["C:\\\\", "/Users/", "/home/", "api_key", "apiKey",
                          "password", "secret", "pickle", "joblib"]) {
      expect(text, `export must not contain ${banned}`).not.toContain(banned);
    }
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    for (const control of [page.getByLabel("Status", { exact: true }),
                           page.getByLabel("Integrity", { exact: true }),
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
    await page.getByRole("button", { name: /Volatility \+ trend \+ combined regimes/ }).click();
    await expect(page.getByText("Regime timeline (effective labels)")).toBeVisible();
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
