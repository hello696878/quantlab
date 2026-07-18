/**
 * Feature Diagnostics Lab E2E coverage (Phase 52.0).
 *
 * Isolation policy (docs/FEATURE_DIAGNOSTICS_RUNBOOK.md): the only writes are
 * the idempotent demo seeds (unique demo_key; they cascade to the
 * Meta-Labeling / Model Validation / Dataset Lineage / Experiment Registry
 * idempotent demo loaders) — real user records are never modified.  A single
 * deliberate exception: the invalid-baseline check clicks "Mark as scope
 * baseline" on a not-held-out demo run and asserts the backend rejects it
 * (409), which writes nothing.  No external network.
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

const HEADER = /Feature Importance, Stability & Drift Diagnostics Lab/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Demo — Held-out permutation importance/ }),
  ).toBeVisible({ timeout: 45_000 });
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

test.describe("feature diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Feature Diagnostics", HEADER);
  });

  test("opens with the held-out / non-causality disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/does not prove causality or profitability/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Model-native impurity reference/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Importance drift without data drift/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by method and integrity", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Method", { exact: true }).selectOption("native_impurity");
    await expect(page.getByRole("button", { name: /Model-native impurity reference/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Demo — Held-out permutation importance/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await page.getByLabel("Integrity", { exact: true }).selectOption("verified_held_out");
    await expect(page.getByRole("button", { name: /Demo — Held-out permutation importance/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Model-native impurity reference/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Model-native impurity reference/ })).toBeVisible();
  });

  test("held-out permutation run: links, importance chart, negative importance", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText("Verified held-out").first()).toBeVisible();
    await expect(page.getByText(/Linked records/i)).toBeVisible();
    await expect(page.getByText(/Leakage-clean: yes/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in Model Validation Lab" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in Dataset Lineage" })).toBeVisible();
    // Importance chart + accessible table; rank-1 wording is descriptive.
    const chart = page.locator("svg[role=img]").first();
    await expect(chart).toHaveAttribute("aria-label", /Aggregate importance bars/);
    await expect(page.getByText(/Highest measured importance under permutation/)).toBeVisible();
    await expect(page.getByText(/mom_signal \(rank 1\)/)).toBeVisible();
    // Negative importance is disclosed in the legend and rendered honestly.
    await expect(page.getByText(/Negative importance \(shown honestly\)/)).toBeVisible();
    await page.getByText(/Full feature table \(accessible alternative\)/i).click();
    await expect(page.locator("details table").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("stability view: rank matrix, pairwise correlations, transparent formula", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText("Rank stability across splits")).toBeVisible();
    await expect(page.getByText("Mean Spearman", { exact: true })).toBeVisible();
    await expect(page.getByText(/Stability score formula/)).toBeVisible();
    await page.getByText(/Pairwise split correlations/).click();
    await expect(page.getByText(/purged-fold-0/).first()).toBeVisible();
    // Less-stable features stay visible in the rank matrix, never hidden.
    const rankMatrix = page.locator("table", { hasText: "Rank σ" }).first();
    await expect(rankMatrix.getByText("moderately stable", { exact: true }).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("correlated feature group is shown without any deletion suggestion", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText(/Correlated feature groups \(1\)/)).toBeVisible();
    await expect(page.getByText(/corr_pair_a, corr_pair_b/)).toBeVisible();
    await expect(page.getByText(/nothing is removed automatically/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("delete this feature");
    expect(body).not.toContain("remove this feature");
    assertNoFailedLocalRequests(failures);
  });

  test("drift views: distribution drift high for the drifting feature, importance drift table", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText("Feature distribution drift")).toBeVisible();
    await expect(page.getByText(/Reference:/)).toBeVisible();
    await expect(page.getByText(/earlier half by timestamp/).first()).toBeVisible();
    // drift_feature row carries a "high" classification pill (drift tables only).
    const driftRow = page.locator("tr", { hasText: "drift_feature" })
      .filter({ has: page.getByText("high", { exact: true }) }).first();
    await expect(driftRow).toBeVisible();
    await expect(page.getByText(/does not prove model failure/i)).toBeVisible();
    await expect(page.getByText("Importance drift (earlier vs later splits)")).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("importance drift without data drift renders honestly; failed run shows its reason", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Importance drift without data drift/ }).click();
    await expect(page.getByText("Declared held-out").first()).toBeVisible();
    // fade_signal is rank/sign unstable while its distribution drift is "none".
    const rankMatrix = page.locator("table", { hasText: "Rank σ" }).first();
    await expect(rankMatrix.getByText("unstable", { exact: true }).first()).toBeVisible();
    const fadeDistRow = page.locator("tr", { hasText: "fade_signal" })
      .filter({ has: page.getByText("none", { exact: true }) }).first();
    await expect(fadeDistRow).toBeVisible();
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await page.getByRole("button", { name: /Leakage-failed validation link/ }).click();
    await expect(page.getByText(/Execution failed:/)).toBeVisible();
    await expect(page.getByText(/leakage-clean validation run/i).first()).toBeVisible();
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline: flagship is marked; a not-held-out run is rejected", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await page.getByRole("button", { name: /Model-native impurity reference/ }).click();
    await expect(page.getByText("Not held-out").first()).toBeVisible();
    await page.getByRole("button", { name: "Mark as scope baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/require held-out evidence/i)).toBeVisible();
    // The 409 from mark-baseline is the expected outcome under test — every
    // other local request must still succeed.
    const unexpected = failures.filter(
      (f) => !(f.url.includes("/mark-baseline") && f.detail === "HTTP 409"),
    );
    expect(unexpected, `unexpected failed requests: ${JSON.stringify(unexpected)}`).toEqual([]);
  });

  test("comparison stays neutral with a per-feature table", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("checkbox", { name: /Select Demo — Held-out permutation importance/ }).check();
    await page.getByRole("checkbox", { name: /Select Demo — Model-native impurity reference/ }).check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare feature-diagnostics runs")).toBeVisible();
    await expect(page.getByText("Per-feature comparison", { exact: false })).toBeVisible();
    await expect(page.getByText(/neither run is labelled better/i)).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("winner");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("export JSON is path- and credential-free with no raw samples", async ({ page }) => {
    await seedDemo(page);
    const response = await page.request.get("/api/feature-diagnostics/export");
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    const parsed = JSON.parse(text);
    expect(parsed.schema_version).toBe("feature_diagnostics_export_v1");
    expect(parsed.note).toMatch(/raw feature samples are not exported/);
    for (const banned of ["C:\\\\", "/Users/", "/home/", "api_key", "apiKey",
                          "secret", "password", "pickle", "joblib"]) {
      expect(text, `export must not contain ${banned}`).not.toContain(banned);
    }
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
  });

  test("no causal / best / recommended wording anywhere in the lab", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText("Verified held-out").first()).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const banned of ["causal feature", "best feature", "recommended feature",
                          "optimal feature", "feature is causal", "proves causality"]) {
      expect(body, `page must not claim "${banned}"`).not.toContain(banned);
    }
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    for (const control of [page.getByLabel("Method", { exact: true }),
                           page.getByLabel("Integrity", { exact: true }),
                           page.getByLabel("Metric", { exact: true }),
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
    await page.getByRole("button", { name: /Demo — Held-out permutation importance/ }).click();
    await expect(page.getByText("Verified held-out").first()).toBeVisible();
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
