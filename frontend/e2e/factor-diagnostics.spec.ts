/**
 * Factor Diagnostics Lab E2E coverage (Phase 59.0).
 *
 * Isolation policy (docs/FACTOR_DIAGNOSTICS_RUNBOOK.md): this spec must run
 * against services configured with an isolated test database. It writes the
 * idempotent demo seeds only (unique demo_key; cascading through the Phase
 * 54/56/57/58 demo loaders) plus one deliberately rejected baseline attempt.
 * It never clears a database and performs no external network access. */

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

const HEADER = /Factor Exposure, Return Decomposition & Macro Sensitivity Lab/;

const BANNED_WORDING =
  /prov(?:es|en) caus|causal factor|prov(?:es|en) alpha|manager skill|predicts returns|guaranteed exposure|recommended factor|best factor model|superior factor|profitable macro trade|production factor model|institutional-grade factor|certified regression|guaranteed forecast/i;

const NEGATION =
  /\b(?:not|never|nothing|neither|nor|without|cannot|isn't|does not|doesn't|no)\b/i;

/**
 * The lab's own disclaimers legitimately contain the banned phrases inside
 * NEGATED sentences ("Nothing here proves causality"). Only an AFFIRMATIVE
 * occurrence is a defect, so negated sentences are dropped before matching
 * rather than trying to encode negation in one regex.
 */
function expectNoAffirmativeOverclaim(body: string): void {
  const affirmative = body
    .split(/(?<=[.;:!?])\s+|\n+/)
    .filter((sentence) => !NEGATION.test(sentence))
    .join("\n");
  expect(affirmative).not.toMatch(BANNED_WORDING);
}

const API = "/api/factor-diagnostics";

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Exact single-factor relationship/ }),
  ).toBeVisible({ timeout: 180_000 });
}

async function runIdByQuery(page: Page, query: string): Promise<number> {
  const listing = await (await page.request.get(
    `${API}/runs?query=${encodeURIComponent(query)}`)).json();
  expect(listing.items.length).toBeGreaterThan(0);
  return listing.items[0].id as number;
}

async function openDetail(page: Page, name: RegExp): Promise<void> {
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("factor-diagnostics-detail")).toBeVisible();
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

test.describe("factor diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    // seeding cascades four upstream demo loaders on a cold database
    test.setTimeout(240_000);
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Factor Diagnostics", HEADER);
  });

  test("opens with the no-causality and no-advice disclaimers", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/proves causality/i).first()).toBeVisible();
    await expect(page.getByText(/never downloaded|ever downloaded/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("factor-runs-table")).toBeVisible();
    await expect(page.getByRole("button", { name: /Baseline candidate/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("button", { name: /Exact single-factor relationship/ }),
    ).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("summary cards and filters narrow the list", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("factor-summary-cards")).toBeVisible();
    await page.getByLabel("Timing", { exact: true }).selectOption("lagged_causal");
    await expect(page.getByRole("button", { name: /Baseline candidate/ })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Exact single-factor relationship/ }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(
      page.getByRole("button", { name: /Exact single-factor relationship/ }),
    ).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("exact single-factor case: the known coefficient is 0.600000", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Exact single-factor");
    const body = await (await page.request.get(
      `${API}/runs/${id}/coefficients`)).json();
    expect(body.items[0].factor_id).toBe("factor_a");
    expect(Math.abs(body.items[0].coefficient - 0.6)).toBeLessThan(1e-9);

    await openDetail(page, /Exact single-factor relationship/);
    await expect(page.getByTestId("factor-coefficients")).toContainText("0.600000");
    await expect(page.getByTestId("coefficient-chart")).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("return decomposition reconciles period by period", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Exact single-factor");
    const periods = await (await page.request.get(`${API}/runs/${id}/periods`)).json();
    expect(periods.items.length).toBeGreaterThan(0);
    for (const row of periods.items) {
      expect(Math.abs(row.measured_return - (row.modelled_return + row.residual)))
        .toBeLessThan(1e-12);
      expect(row.reconciliation_state).toBe("reconciled");
    }
    await openDetail(page, /Exact single-factor relationship/);
    await expect(page.getByTestId("factor-reconciliation")).toBeVisible();
    await expect(page.getByTestId("factor-reconciliation")).toContainText(/reconciled/);
    await expect(page.getByTestId("factor-periods")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("two-factor case exposes both coefficients and the intercept", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Two known coefficients");
    const body = await (await page.request.get(
      `${API}/runs/${id}/coefficients`)).json();
    const values = Object.fromEntries(
      body.items.map((r: { factor_id: string; coefficient: number }) =>
        [r.factor_id, r.coefficient]));
    expect(Math.abs(values.factor_a - 1.5)).toBeLessThan(1e-9);
    expect(Math.abs(values.factor_b + 0.5)).toBeLessThan(1e-9);
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(Math.abs(run.intercept - 0.002)).toBeLessThan(1e-9);
    await openDetail(page, /Two known coefficients/);
    await expect(page.getByTestId("factor-coefficients")).toContainText("1.500000");
    await expect(page.getByTestId("factor-coefficients")).toContainText("-0.500000");
    assertNoFailedLocalRequests(failures);
  });

  test("intercept-and-residual case publishes standard errors and adjusted p-values", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Non-zero intercept and residual");
    const body = await (await page.request.get(
      `${API}/runs/${id}/coefficients`)).json();
    const a = body.items.find((r: { factor_id: string }) => r.factor_id === "factor_a");
    expect(a.standard_error).toBeGreaterThan(0);
    expect(Math.abs(a.t_statistic - a.coefficient / a.standard_error)).toBeLessThan(1e-6);
    expect(a.p_bh).not.toBeNull();
    await openDetail(page, /Non-zero intercept and residual/);
    await expect(page.getByTestId("factor-coefficients")).toContainText("0.800000");
    await expect(page.getByTestId("factor-coefficients")).toContainText(/Multiple-testing family/);
    await expect(page.getByTestId("factor-coefficients"))
      .toContainText(/not evidence of causality/);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("an exact fit withholds standard errors instead of showing infinity", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Exact single-factor relationship/);
    await expect(page.getByTestId("factor-coefficients"))
      .toContainText(/residual variance is zero/);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("constant factor is flagged and its VIF stays unavailable", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Constant factor column/);
    await expect(page.getByTestId("factor-warnings")).toContainText(/constant factor column/i);
    await expect(page.getByTestId("factor-coefficients")).toContainText("unavailable");
    await expect(page.getByTestId("factor-correlation")).toContainText("unavailable");
    assertNoFailedLocalRequests(failures);
  });

  test("duplicate factors leave a labelled rank-deficient design", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Duplicate factor column");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.rank_status).toBe("rank_deficient_descriptive");
    await openDetail(page, /Duplicate factor column/);
    await expect(page.getByTestId("factor-warnings")).toContainText(/RANK DEFICIENT/);
    await expect(page.getByTestId("factor-correlation")).toContainText(/Rank/);
    assertNoFailedLocalRequests(failures);
  });

  test("near-collinear design warns about the condition number", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Near-collinear factors/);
    await expect(page.getByTestId("factor-correlation")).toContainText(/condition number/i);
    await expect(page.getByTestId("factor-correlation")).toContainText(/not a universal rule/);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("insufficient observations fail honestly with the stated reason", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Insufficient observations");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.status).toBe("failed");
    expect(run.error_message).toMatch(/cannot identify/);
    await openDetail(page, /Insufficient observations/);
    await expect(page.getByTestId("factor-diagnostics-detail"))
      .toContainText(/cannot identify/);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("a zero-variance target leaves R-squared unavailable", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Zero-variance target");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.r_squared).toBeNull();
    expect(run.fit.r_squared_note).toMatch(/zero variance/);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("lagged causal timing is verified and availability precedes the period", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Lagged causal alignment");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.integrity_status).toBe("verified_trailing_estimation");
    const observations = await (await page.request.get(
      `${API}/runs/${id}/observations`)).json();
    const periods = await (await page.request.get(`${API}/runs/${id}/periods`)).json();
    const cutoff = new Map<number, string>(
      periods.items.map((p: { period_index: number; information_available_at: string }) =>
        [p.period_index, p.information_available_at]));
    for (const row of observations.items) {
      expect(row.knowable_at <= cutoff.get(row.period_index)!).toBe(true);
    }
    await openDetail(page, /Lagged causal alignment/);
    await expect(page.getByTestId("factor-observations")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("contemporaneous alignment is descriptive and never called predictive", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Contemporaneous alignment/);
    await expect(page.getByTestId("factor-warnings"))
      .toContainText(/descriptive association only/);
    await expect(page.getByTestId("factor-warnings"))
      .toContainText(/never ex-ante or predictive/);
    assertNoFailedLocalRequests(failures);
  });

  test("future-looking alignment is invalid and cannot become a baseline", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Future-looking alignment/);
    await expect(page.getByText("Invalid").first()).toBeVisible();
    await expect(page.getByTestId("factor-warnings")).toContainText(/INVALID timing/);
    await page.getByRole("button", { name: "Mark as comparison baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 20_000 });
    const unexpected = failures.filter((f) => !f.url.includes("mark-baseline"));
    assertNoFailedLocalRequests(unexpected);
  });

  test("rolling windows are trailing and show the exposure change", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Rolling exposure change");
    const rolling = await (await page.request.get(`${API}/runs/${id}/rolling`)).json();
    expect(rolling.items.length).toBeGreaterThan(2);
    const first = rolling.items[0].coefficients.factor_a;
    const last = rolling.items[rolling.items.length - 1].coefficients.factor_a;
    expect(Math.abs(first - 0.5)).toBeLessThan(1e-6);
    expect(Math.abs(last - 1.5)).toBeLessThan(1e-6);
    await openDetail(page, /Rolling exposure change/);
    await expect(page.getByTestId("factor-rolling")).toBeVisible();
    await expect(page.getByTestId("rolling-chart")).toBeVisible();
    await expect(page.getByTestId("factor-rolling"))
      .toContainText(/never reads an observation after its own end/);
    await expect(page.getByTestId("factor-stability")).toBeVisible();
    await expect(page.getByTestId("factor-stability"))
      .toContainText(/not a permanent property/);
    assertNoFailedLocalRequests(failures);
  });

  test("portfolio versus benchmark active exposure is a plain difference", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Portfolio versus benchmark");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.exposure_comparison.length).toBeGreaterThan(0);
    for (const row of run.exposure_comparison) {
      expect(Math.abs(row.active_exposure
        - (row.portfolio_exposure - row.benchmark_exposure))).toBeLessThan(1e-12);
    }
    await openDetail(page, /Portfolio versus benchmark/);
    await expect(page.getByTestId("factor-benchmark")).toBeVisible();
    await expect(page.getByTestId("factor-benchmark"))
      .toContainText(/neither desirable nor undesirable/);
    assertNoFailedLocalRequests(failures);
  });

  test("regime-linked view uses stored assignments and marks rare regimes", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "STORED regime assignment");
    const regimes = await (await page.request.get(`${API}/runs/${id}/regimes`)).json();
    expect(regimes.items.length).toBeGreaterThan(1);
    expect(regimes.items.some((r: { rare: boolean }) => r.rare)).toBe(true);
    await openDetail(page, /Exposure by STORED regime assignment/);
    await expect(page.getByTestId("factor-regimes")).toBeVisible();
    await expect(page.getByTestId("factor-regimes")).toContainText(/never recomputed/);
    await expect(page.getByTestId("factor-regimes")).toContainText("rare");
    assertNoFailedLocalRequests(failures);
  });

  test("stress linkage multiplies exposures by SUPPLIED shocks only", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Exposure-implied factor shock/);
    await expect(page.getByTestId("factor-stress")).toBeVisible();
    await expect(page.getByTestId("factor-stress"))
      .toContainText(/measured_exposure_k x supplied_shock_k/);
    await expect(page.getByTestId("factor-stress")).toContainText(/undefined/);
    await expect(page.getByTestId("factor-warnings"))
      .toContainText(/no hedge or reallocation follows/);
    assertNoFailedLocalRequests(failures);
  });

  test("attribution linkage stays complementary to Brinson", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Active return decomposed by factor exposure/);
    await expect(page.getByTestId("factor-attribution")).toBeVisible();
    await expect(page.getByTestId("factor-attribution"))
      .toContainText(/not interchangeable/);
    await expect(page.getByTestId("factor-attribution"))
      .toContainText(/residual here is not alpha/);
    await expect(page.getByTestId("factor-attribution"))
      .toContainText(/transaction cost stays inside/);
    assertNoFailedLocalRequests(failures);
  });

  test("held-out metrics never refit on the held-out rows", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Held-out evaluation");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.held_out.training_observations).toBeGreaterThan(0);
    expect(run.held_out.held_out_observations).toBeGreaterThan(0);
    await openDetail(page, /Held-out evaluation on a stored validation split/);
    await expect(page.getByTestId("factor-heldout")).toBeVisible();
    await expect(page.getByTestId("factor-heldout"))
      .toContainText(/nothing is refitted on held-out data/);
    await expect(page.getByTestId("factor-heldout")).toContainText(/TRAINING mean/);
    assertNoFailedLocalRequests(failures);
  });

  test("macro factor without a release timestamp states the assumption", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Macro factor with no release timestamp/);
    await expect(page.getByTestId("factor-warnings"))
      .toContainText(/availability is ASSUMED/);
    await expect(page.getByTestId("factor-definitions")).toContainText("basis_point_change");
    assertNoFailedLocalRequests(failures);
  });

  test("sensitivity scenarios stay neutral and keep the base once", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Non-zero intercept and residual");
    const sensitivity = await (await page.request.get(
      `${API}/runs/${id}/sensitivity`)).json();
    expect(sensitivity.items.filter((s: { is_base: boolean }) => s.is_base).length).toBe(1);
    expect(sensitivity.note).toMatch(/no scenario is labelled best/i);
    await openDetail(page, /Non-zero intercept and residual/);
    await expect(page.getByTestId("factor-sensitivity")).toBeVisible();
    await expect(page.getByTestId("factor-sensitivity"))
      .toContainText(/No scenario is labelled best, optimal or recommended/);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline behaviour: an eligible run can be marked, and it is only a reference", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Baseline candidate");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.integrity_status).toBe("verified_causal_lag");
    expect(run.is_baseline).toBe(true);
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    const rows = page.getByTestId("factor-runs-table").locator("tbody tr");
    await rows.nth(0).getByRole("checkbox").check();
    await rows.nth(1).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByTestId("factor-compare")).toBeVisible();
    await expect(page.getByText(/no run is better, superior, preferred or recommended/i))
      .toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
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
    expect(payload.schema_version).toBe("factor_diagnostics_export_v1");
    expect(payload.disclaimer).toMatch(/proves causality/);
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls are dark and units are visible in the detail", async ({ page }) => {
    await seedDemo(page);
    await expectDarkBackground(page.getByLabel("Timing", { exact: true }));
    await expectDarkBackground(page.getByLabel("Integrity", { exact: true }));
    await expectDarkBackground(page.getByLabel("Search", { exact: true }));
    await openDetail(page, /Non-zero intercept and residual/);
    await expect(page.getByTestId("factor-definitions")).toContainText("return_fraction");
    await expect(page.getByTestId("factor-coefficients"))
      .toContainText(/target return per 1/);
    await expect(page.getByTestId("factor-periods")).toContainText("%");
    assertNoFailedLocalRequests(failures);
  });

  test("desktop, 1024 and 768 stay usable without overlap", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Non-zero intercept and residual/);
    for (const width of [1440, 1024, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(150);
      await assertNoHorizontalOverflow(page);
      await expect(page.getByTestId("factor-coefficients")).toBeVisible();
    }
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no NaN, no stack trace and no affirmative overclaim anywhere", async ({ page }) => {
    await seedDemo(page);
    expectNoAffirmativeOverclaim((await page.locator("body").innerText()));
    for (const name of [/Exact single-factor relationship/,
                        /Non-zero intercept and residual/,
                        /Duplicate factor column/,
                        /Exposure by STORED regime assignment/,
                        /Held-out evaluation on a stored validation split/]) {
      await openDetail(page, name);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
      expectNoAffirmativeOverclaim(await page.locator("body").innerText());
      await page.getByRole("button", { name: "← Back to runs" }).click();
      await expect(page.getByTestId("factor-runs-table")).toBeVisible();
    }
    assertNoFailedLocalRequests(failures);
  });
});
