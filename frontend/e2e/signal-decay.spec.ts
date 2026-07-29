/**
 * Signal Decay Lab E2E coverage (Phase 60.0).
 *
 * Isolation policy (docs/SIGNAL_DECAY_RUNBOOK.md): this spec must run
 * against services configured with an isolated test database. It writes the
 * idempotent demo seeds only (unique demo_key; cascading through the Phase
 * 54/52/55/59 demo loaders) plus one deliberately rejected baseline
 * attempt. It never clears a database and performs no external network
 * access. */

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

const HEADER =
  /Signal Decay, Forecast Horizon, Turnover & Implementation Lag Lab/;

const BANNED_WORDING =
  /proven signal|validated alpha|predicts returns|profitable signal|optimal horizon|best holding period|recommended lag|guaranteed decay|production signal|institutional-grade signal|certified signal|guaranteed performance/i;

const NEGATION =
  /\b(?:not|never|nothing|neither|nor|without|cannot|isn't|does not|doesn't|no)\b/i;

/**
 * The lab's own disclaimers legitimately contain banned phrases inside
 * NEGATED sentences ("Nothing here proves predictability"). Only an
 * AFFIRMATIVE occurrence is a defect, so negated sentences are dropped
 * before matching.
 */
function expectNoAffirmativeOverclaim(body: string): void {
  const affirmative = body
    .split(/(?<=[.;:!?])\s+|\n+/)
    .filter((sentence) => !NEGATION.test(sentence))
    .join("\n");
  expect(affirmative).not.toMatch(BANNED_WORDING);
}

const API = "/api/signal-decay";

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Perfect positive one-horizon/ }),
  ).toBeVisible({ timeout: 240_000 });
}

async function runIdByQuery(page: Page, query: string): Promise<number> {
  const listing = await (await page.request.get(
    `${API}/runs?query=${encodeURIComponent(query)}`)).json();
  expect(listing.items.length).toBeGreaterThan(0);
  return listing.items[0].id as number;
}

async function openDetail(page: Page, name: RegExp): Promise<void> {
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("signal-decay-detail")).toBeVisible();
}

async function expectDarkBackground(
  control: ReturnType<Page["getByLabel"]>,
): Promise<void> {
  const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
  const rgb = bg.match(/rgba?\(([^)]+)\)/);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
    expect((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255,
      `background ${bg} should be dark`).toBeLessThan(0.5);
    return;
  }
  const oklch = bg.match(/oklch\(\s*([\d.]+)/);
  expect(oklch, `background '${bg}' should be rgb(a) or oklch()`).not.toBeNull();
  expect(Number.parseFloat(oklch![1]), `background ${bg} should be dark`)
    .toBeLessThan(0.5);
}

test.describe("signal decay lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    // seeding cascades several upstream demo loaders on a cold database
    test.setTimeout(300_000);
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Signal Decay Lab", HEADER);
  });

  test("opens with the no-predictability and no-advice disclaimers", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/proves predictability/i).first()).toBeVisible();
    await expect(page.getByText(/overlap/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("signal-runs-table")).toBeVisible();
    await expect(page.getByRole("button", { name: /Baseline candidate/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 60_000 });
    await expect(
      page.getByRole("button", { name: /Perfect positive one-horizon/ }),
    ).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("summary cards and filters narrow the list", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("signal-summary-cards")).toBeVisible();
    await page.getByLabel("Overlap", { exact: true }).selectOption("overlapping");
    await expect(page.getByRole("button", { name: /Overlapping horizon-4/ })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Perfect positive one-horizon/ }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(
      page.getByRole("button", { name: /Perfect positive one-horizon/ }),
    ).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("perfect positive example: the horizon-1 statistic is exactly 1", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Perfect positive");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const raw = horizons.items.find(
      (r: { outcome_scope: string; selection: string }) =>
        r.outcome_scope === "raw" && r.selection === "overlapping");
    expect(Math.abs(raw.spearman - 1)).toBeLessThan(1e-12);
    expect(Math.abs(raw.pearson - 1)).toBeLessThan(1e-9);
    await openDetail(page, /Perfect positive one-horizon/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("1.0000");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("perfect negative example reads -1", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Perfect negative");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    expect(Math.abs(horizons.items[0].spearman + 1)).toBeLessThan(1e-12);
    await openDetail(page, /Perfect negative relationship/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("-1.0000");
    assertNoFailedLocalRequests(failures);
  });

  test("constant signal and outcome stay unavailable with reasons", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Constant signal/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("unavailable");
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await openDetail(page, /Constant outcome/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("unavailable");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("tie-heavy example shows the tie policy and a conservative spread", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Heavy signal ties");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    expect(horizons.items[0].top_minus_bottom).toBeNull();
    await openDetail(page, /Heavy signal ties/);
    await expect(page.getByTestId("signal-decay-detail")).toContainText(/Tie policy/i);
    await expect(page.getByTestId("signal-decay-detail")).toContainText("average");
    assertNoFailedLocalRequests(failures);
  });

  test("cross-sectional rank IC uses each timestamp's own universe", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Cross-sectional rank IC");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const raw = horizons.items[0];
    expect(Math.abs(raw.mean_cross_sectional_ic - 1)).toBeLessThan(1e-12);
    await openDetail(page, /Cross-sectional rank IC/);
    await expect(page.getByTestId("signal-decay-detail"))
      .toContainText(/own universe|own eligible universe|own stored grid|contemporaneous/i);
    assertNoFailedLocalRequests(failures);
  });

  test("decay curve shows sample counts and overlap per horizon", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Decaying association across horizons/);
    await expect(page.getByTestId("decay-chart")).toBeVisible();
    const table = page.getByTestId("signal-decay-curve");
    await expect(table).toContainText("Overlap");
    await expect(table).toContainText("Obs.");
    await expect(table).toContainText(/no horizon is called optimal/);
    await expect(page.getByTestId("signal-decay-summary"))
      .toContainText("First sign change");
    assertNoFailedLocalRequests(failures);
  });

  test("sign-changing example locates the first sign change, no optimal horizon", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Sign-changing");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    const spearmanDecay = run.decay.find(
      (d: { statistic: string }) => d.statistic === "spearman");
    expect(spearmanDecay.first_sign_change_horizon).toBe(2);
    await openDetail(page, /Sign-changing association/);
    await expect(page.getByTestId("signal-decay-summary"))
      .toContainText("First sign change");
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/optimal horizon/i);
    assertNoFailedLocalRequests(failures);
  });

  test("overlap warning and p-value limitation are visible", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Overlapping horizon-4");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.overlap_status).toBe("overlapping");
    await openDetail(page, /Overlapping horizon-4/);
    await expect(page.getByTestId("signal-warnings"))
      .toContainText(/not independent/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("⚠");
    assertNoFailedLocalRequests(failures);
  });

  test("deterministic non-overlapping selection is shown beside the full rows", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Deterministic non-overlapping");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const selected = horizons.items.find(
      (r: { selection: string }) => r.selection === "non_overlapping");
    expect(selected.observations).toBe(9);
    await openDetail(page, /Deterministic non-overlapping selection/);
    await expect(page.getByTestId("signal-non-overlap")).toBeVisible();
    await expect(page.getByTestId("signal-non-overlap"))
      .toContainText(/at or after the previous exit/);
    assertNoFailedLocalRequests(failures);
  });

  test("bucket boundaries, counts and the non-monotonic example render", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Monotonic quantile buckets/);
    await expect(page.getByTestId("signal-buckets")).toBeVisible();
    await expect(page.getByTestId("signal-buckets")).toContainText("Score min");
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await expect(page.getByTestId("signal-runs-table")).toBeVisible();
    await openDetail(page, /Non-monotonic \(U-shaped\) buckets/);
    await expect(page.getByTestId("signal-buckets")).toBeVisible();
    const id = await runIdByQuery(page, "Non-monotonic");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const mono = horizons.items[0].detail.monotonicity;
    expect(mono.adjacent_violations).toBeGreaterThan(0);
    assertNoFailedLocalRequests(failures);
  });

  test("turnover timeline: high churn versus stable membership", async ({ page }) => {
    await seedDemo(page);
    const highId = await runIdByQuery(page, "High-turnover");
    const high = await (await page.request.get(`${API}/runs/${highId}`)).json();
    expect(high.turnover_summary.mean_one_way_turnover).toBeGreaterThan(0.5);
    const lowId = await runIdByQuery(page, "Stable-membership");
    const low = await (await page.request.get(`${API}/runs/${lowId}`)).json();
    expect(low.turnover_summary.mean_one_way_turnover).toBe(0);
    expect(low.turnover_summary.mean_jaccard_top).toBe(1);
    await openDetail(page, /Stable-membership low-turnover/);
    await expect(page.getByTestId("signal-turnover")).toBeVisible();
    await expect(page.getByTestId("signal-turnover"))
      .toContainText("unavailable (no prior)");
    assertNoFailedLocalRequests(failures);
  });

  test("implementation-delay surface shifts entry and exit correctly", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Implementation-delay");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const raw = horizons.items.filter(
      (r: { outcome_scope: string; selection: string }) =>
        r.outcome_scope === "raw" && r.selection === "overlapping");
    const lags = Array.from(
      new Set(raw.map((r: { entry_lag: number }) => r.entry_lag)));
    expect(lags.sort()).toEqual([0, 1, 2]);
    const h1 = raw.filter((r: { horizon: number }) => r.horizon === 1)
      .sort((a: { entry_lag: number }, b: { entry_lag: number }) => a.entry_lag - b.entry_lag);
    expect(Math.abs(h1[0].spearman)).toBeGreaterThan(Math.abs(h1[2].spearman));
    await openDetail(page, /Implementation-delay degradation/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText("Lag");
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/recommended lag/i);
    assertNoFailedLocalRequests(failures);
  });

  test("cost-adjusted reference: gross positive, net non-positive", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "cost-adjusted non-positive");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const raw = horizons.items.find(
      (r: { outcome_scope: string }) => r.outcome_scope === "raw");
    expect(raw.top_minus_bottom).toBeGreaterThan(0);
    expect(raw.cost_adjusted_spread).toBeLessThanOrEqual(0);
    await openDetail(page, /Gross-positive, cost-adjusted non-positive/);
    await expect(page.getByTestId("signal-cost")).toBeVisible();
    await expect(page.getByTestId("signal-cost")).toContainText(/per side/);
    await expect(page.getByTestId("signal-cost"))
      .toContainText(/gross top-minus-bottom spread minus/);
    assertNoFailedLocalRequests(failures);
  });

  test("regime results mark rare regimes and pin stored assignments", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "STORED regime");
    const regimes = await (await page.request.get(
      `${API}/runs/${id}/regimes`)).json();
    expect(regimes.items.some((r: { rare: boolean }) => r.rare)).toBe(true);
    await openDetail(page, /Signal decay by STORED regime/);
    await expect(page.getByTestId("signal-regimes")).toBeVisible();
    await expect(page.getByTestId("signal-regimes")).toContainText(/never recomputed/);
    await expect(page.getByTestId("signal-regimes")).toContainText("rare");
    assertNoFailedLocalRequests(failures);
  });

  test("held-out results use frozen train thresholds, no refitting", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Held-out evaluation");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.held_out.training_observations).toBeGreaterThan(0);
    expect(run.held_out.held_out_observations).toBeGreaterThan(0);
    expect(run.held_out.frozen_bucket_thresholds).not.toBeNull();
    await openDetail(page, /Held-out evaluation on a stored validation split/);
    await expect(page.getByTestId("signal-heldout")).toBeVisible();
    await expect(page.getByTestId("signal-heldout"))
      .toContainText(/nothing is refitted/);
    assertNoFailedLocalRequests(failures);
  });

  test("future-looking example is invalid and cannot become a baseline", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Future-looking outcome/);
    await expect(page.getByText("Invalid").first()).toBeVisible();
    await expect(page.getByTestId("signal-warnings")).toContainText(/timing violation/);
    await page.getByRole("button", { name: "Mark as comparison baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 20_000 });
    const unexpected = failures.filter((f) => !f.url.includes("mark-baseline"));
    assertNoFailedLocalRequests(unexpected);
  });

  test("factor-residual comparison keeps raw and residual scopes separate", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "factor-residualised");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const scopes = new Set(horizons.items.map(
      (r: { outcome_scope: string }) => r.outcome_scope));
    expect(scopes.has("raw")).toBe(true);
    expect(scopes.has("factor_residual")).toBe(true);
    await openDetail(page, /Raw versus factor-residualised/);
    await expect(page.getByTestId("signal-factor-residual")).toBeVisible();
    await expect(page.getByTestId("signal-factor-residual"))
      .toContainText(/separate rows/);
    assertNoFailedLocalRequests(failures);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    const rows = page.getByTestId("signal-runs-table").locator("tbody tr");
    await rows.nth(0).getByRole("checkbox").check();
    await rows.nth(1).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByTestId("signal-compare")).toBeVisible();
    await expect(page.getByText(/no winner is declared/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline behaviour: the eligible candidate is marked", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Baseline candidate");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.is_baseline).toBe(true);
    expect(run.integrity_status).toBe("verified_point_in_time");
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("export downloads JSON without paths or credentials", async ({ page }) => {
    await seedDemo(page);
    const payload = await (await page.request.get(`${API}/export`)).json();
    const text = JSON.stringify(payload);
    for (const banned of ["C:\\\\", "/home/", "password", "api_key", "secret",
                          "quantlab.db"]) {
      expect(text).not.toContain(banned);
    }
    expect(payload.schema_version).toBe("signal_decay_export_v1");
    expect(payload.disclaimer).toMatch(/proves/);
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls are dark and units are visible in the detail", async ({ page }) => {
    await seedDemo(page);
    await expectDarkBackground(page.getByLabel("Overlap", { exact: true }));
    await expectDarkBackground(page.getByLabel("Integrity", { exact: true }));
    await expectDarkBackground(page.getByLabel("Search", { exact: true }));
    await openDetail(page, /Decaying association across horizons/);
    await expect(page.getByTestId("signal-decay-detail")).toContainText(/unit score/);
    await expect(page.getByTestId("signal-decay-curve")).toContainText(/observations/);
    await expect(page.getByTestId("signal-buckets")).toContainText("%");
    assertNoFailedLocalRequests(failures);
  });

  test("desktop, 1024 and 768 stay usable without overlap", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Decaying association across horizons/);
    for (const width of [1440, 1024, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(150);
      await assertNoHorizontalOverflow(page);
      await expect(page.getByTestId("signal-decay-curve")).toBeVisible();
    }
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no NaN, no stack trace and no affirmative overclaim anywhere", async ({ page }) => {
    await seedDemo(page);
    expectNoAffirmativeOverclaim(await page.locator("body").innerText());
    for (const name of [/Perfect positive one-horizon/,
                        /Decaying association across horizons/,
                        /Gross-positive, cost-adjusted non-positive/,
                        /Held-out evaluation on a stored validation split/,
                        /Raw versus factor-residualised/]) {
      await openDetail(page, name);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
      expectNoAffirmativeOverclaim(await page.locator("body").innerText());
      await page.getByRole("button", { name: "← Back to runs" }).click();
      await expect(page.getByTestId("signal-runs-table")).toBeVisible();
    }
    assertNoFailedLocalRequests(failures);
  });
});
