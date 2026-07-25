/**
 * Portfolio Stress Lab E2E coverage (Phase 57.0).
 *
 * Isolation policy (docs/PORTFOLIO_STRESS_RUNBOOK.md): the only writes are
 * the idempotent demo seeds (unique demo_key; they cascade through the
 * Phase 56/55 idempotent demo loaders) plus one deliberately rejected
 * baseline attempt — real user records are never modified.  No external
 * network.
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

const HEADER = /Portfolio Stress Testing, Scenario Shock & Drawdown Attribution Lab/;

// affirmative claims only — the lab's own disclaimers legitimately contain
// negations such as "no scenario is a worst case"
const BANNED_WORDING =
  /this is the worst case|the worst[- ]case scenario|worst[- ]case loss|guaranteed loss|guarantees protection|guaranteed protection|optimal hedge|safest portfolio|we recommend|recommended hedge|recommended action:|will lose|predicted loss|crash forecast|stress-proof|risk-free|zero risk/i;

const API = "/api/portfolio-stress";

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  // the cascading Phase 56/55/54 demo loaders are slow on a cold, empty
  // database; the beforeEach raises the per-test budget to match
  await expect(
    page.getByRole("button", { name: /Flagship combined stress on the ERC book/ }),
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
  await expect(page.getByTestId("portfolio-stress-detail")).toBeVisible();
}

test.describe("portfolio stress lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    // seeding cascades four labs' demo loaders on a cold database
    test.setTimeout(240_000);
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Portfolio Stress Lab", HEADER);
  });

  test("opens with honest-scope disclaimers and no banned wording", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/not predictions/i).first()).toBeVisible();
    await expect(page.getByText(/no scenario is a worst case/i).first()).toBeVisible();
    await expect(page.getByText(/nothing here hedges, rebalances, trades/i).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(BANNED_WORDING);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently with 16 documented cases", async ({ page }) => {
    await seedDemo(page);
    const summary = await (await page.request.get(`${API}/summary`)).json();
    expect(summary.runs).toBe(16);
    expect(summary.completed).toBe(16);
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("button", { name: /Flagship combined stress on the ERC book/ }),
    ).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by scenario type and integrity", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Scenario type", { exact: true }).selectOption("historical_window");
    await expect(page.getByRole("button", { name: /Historical window replay/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Volatility x2\.5/ })).toHaveCount(0);
    await page.getByLabel("Integrity", { exact: true }).selectOption("invalid");
    await expect(page.getByRole("button", { name: /Invalid future-looking ex-ante claim/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Historical window replay/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Volatility x2\.5/ })).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("flagship: contributions reconcile and both effects stay separate", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Flagship combined stress");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    const assets = await (await page.request.get(`${API}/runs/${id}/asset-results`)).json();
    const sum = assets.items.reduce(
      (a: number, r: { contribution: number | null }) => a + (r.contribution ?? 0), 0);
    expect(Math.abs(sum - run.reconciliation.direct_shock_return)).toBeLessThan(1e-9);
    expect(run.risk_summary.stressed_volatility).toBeGreaterThan(run.risk_summary.baseline_volatility);
    expect(run.scenario_pnl).toBeLessThan(0);

    await openDetail(page, /Flagship combined stress on the ERC book/);
    await expect(page.getByTestId("stress-reconciliation")).toBeVisible();
    await expect(page.getByText(/reported separately, never mixed into P&L/)).toBeVisible();
    await expect(page.getByTestId("contribution-waterfall")).toBeVisible();
    await expect(page.getByTestId("stress-risk")).toBeVisible();
    await expect(page.getByTestId("stress-sensitivity")).toBeVisible();
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });

  test("shock units convert exactly as documented", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Shock units side by side");
    const assets = await (await page.request.get(`${API}/runs/${id}/asset-results`)).json();
    const byId = new Map<string, number | null>(
      assets.items.map((r: { asset_id: string; shock: number | null }) =>
        [r.asset_id, r.shock] as const),
    );
    expect(byId.get("lowvol-a")).toBeCloseTo(-0.025, 10); // −250 bps
    expect(byId.get("midvol-a")).toBeCloseTo(-0.03, 10);  // −0.03 return
    expect(byId.get("highvol-a")).toBeCloseTo(-0.03, 10); // −3 percent
    await openDetail(page, /Shock units side by side/);
    await expect(
      page.getByText(/Units: return = decimal, percent = value\/100, bps = value\/10000/),
    ).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("missing-shock policy 'unavailable' stays honestly partial", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Partial scenario under the 'unavailable' policy/);
    await expect(page.getByText("partial").first()).toBeVisible();
    await expect(page.getByTestId("stress-warnings")).toContainText(/missing-shock policy/);
    await expect(page.getByText(/Drifted weights unavailable/)).toBeVisible();
    await expect(page.getByText(/unavailable \(no shock under the missing-shock policy\)/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("future-looking ex-ante claim is invalid and cannot become a baseline", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Invalid future-looking");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.integrity_status).toBe("invalid");
    const attempt = await page.request.post(`${API}/runs/${id}/mark-baseline`, { data: {} });
    expect(attempt.status()).toBe(409);
    await openDetail(page, /Invalid future-looking ex-ante claim/);
    await expect(page.getByText("Invalid", { exact: true }).first()).toBeVisible();
    await expect(page.getByTestId("stress-warnings")).toContainText(/never labelled ex-ante/);
    assertNoFailedLocalRequests(failures);
  });

  test("pure volatility stress changes risk estimates, never P&L", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Volatility x2.5");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.scenario_return).toBe(0);
    expect(run.risk_summary.stressed_volatility).toBeCloseTo(
      2.5 * run.risk_summary.baseline_volatility, 10);
    await openDetail(page, /Volatility x2\.5 \(risk estimate only\)/);
    await expect(page.getByTestId("stress-risk")).toContainText(/Stressed volatility/i);
    await expect(page.getByText(/not automatically worse/)).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("non-PSD supplied correlation: honest refusal vs explicit repair", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Supplied non-PSD correlation — honest unavailability/);
    await expect(page.getByTestId("cov-stress-unavailable")).toContainText(/no silent repair/);
    await expect(page.getByText("partial").first()).toBeVisible();
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await openDetail(page, /Supplied non-PSD correlation — explicit repair/);
    await expect(page.getByTestId("cov-stress-repaired")).toContainText(
      /repaired under the explicit eigenvalue_floor policy/);
    // the disclosed values must describe the repaired matrix, with the
    // requested values shown beside them
    await expect(page.getByTestId("cov-stress-repaired")).toContainText(
      /requested .* → effective/);
    assertNoFailedLocalRequests(failures);
  });

  test("liquidity/cost stress: copied model, participation, honest impact", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Liquidity and cost stress");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    const cb = run.cost_stress;
    expect(cb.stressed_model_fingerprint).not.toBe(cb.base_model_fingerprint);
    expect(cb.stressed.components.spread).toBeCloseTo(3 * cb.base.components.spread, 12);
    expect(cb.stressed.components.commission).toBeCloseTo(cb.base.components.commission, 12);
    expect(cb.participation.above_threshold).toBe(true);
    await openDetail(page, /Liquidity and cost stress on the linked cost model/);
    await expect(page.getByTestId("stress-cost")).toBeVisible();
    await expect(page.getByText(/never modified/)).toBeVisible();
    await expect(page.getByTestId("stress-participation")).toContainText(/above the explicit threshold/);
    await expect(page.getByText(/Completeness: partial/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("post-shock drift breaches constraints without auto-rebalancing", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Post-shock constraint breaches");
    const rows = await (await page.request.get(
      `${API}/runs/${id}/constraint-results`)).json();
    // the breaches must come from the DRIFTED book, not the stored one
    expect(rows.items.length).toBeGreaterThan(0);
    expect(rows.items.every((r: { book: string }) => r.book === "drifted")).toBe(true);
    await openDetail(page, /Post-shock constraint breaches/);
    await expect(page.getByTestId("stress-constraints")).toBeVisible();
    await expect(
      page.getByTestId("stress-constraints").getByRole("row", { name: /drifted/ }).first(),
    ).toBeVisible();
    await expect(page.getByText(/nothing is rebalanced automatically/i).first()).toBeVisible();
    await expect(page.getByTestId("stress-warnings")).toContainText(/no automatic rebalancing/);
    assertNoFailedLocalRequests(failures);
  });

  test("drawdown episodes and deepest-episode attribution render", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Drawdown episodes on the rebalanced book");
    const episodes = await (await page.request.get(`${API}/runs/${id}/episodes`)).json();
    expect(episodes.items.length).toBeGreaterThan(0);
    const attribution = await (await page.request.get(`${API}/runs/${id}/attribution`)).json();
    expect(attribution.items.length).toBeGreaterThan(0);
    await openDetail(page, /Drawdown episodes on the rebalanced book/);
    await expect(page.getByTestId("drawdown-chart")).toBeVisible();
    await expect(page.getByTestId("stress-drawdown")).toContainText(/trailing-only/);
    await expect(page.getByTestId("stress-attribution")).toBeVisible();
    await expect(page.getByTestId("stress-attribution")).toContainText(/approximation labelled/);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("full-sample historical window is labelled descriptive", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Full-sample window \(descriptive only\)/);
    await expect(page.getByText("Full-sample descriptive").first()).toBeVisible();
    await expect(page.getByTestId("stress-warnings")).toContainText(/descriptive only/);
    assertNoFailedLocalRequests(failures);
  });

  test("compare reports differences neutrally with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    await page
      .getByRole("row", { name: /Flagship combined stress/ })
      .getByRole("checkbox")
      .check();
    await page
      .getByRole("row", { name: /Volatility x2\.5/ })
      .getByRole("checkbox")
      .check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByRole("heading", { name: "Compare portfolio-stress runs" })).toBeVisible();
    await expect(page.getByText(/no scenario outcome is declared better, safer, or recommended/)).toBeVisible();
    await expect(page.getByText(/fp: differs/).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(BANNED_WORDING);
    assertNoFailedLocalRequests(failures);
  });

  test("export honours the active filter and downloads JSON", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Scenario type", { exact: true }).selectOption("volatility_stress");
    await expect(page.getByRole("button", { name: /Volatility x2\.5/ })).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/quantlab-portfolio-stress-.*\.json/);
    await expect(page.getByText(/Export ready/)).toBeVisible();
    // the filter reached the backend: only volatility_stress runs exported
    const filtered = await (await page.request.get(
      `${API}/export?scenario_type=volatility_stress`)).json();
    expect(filtered.filters.scenario_type).toBe("volatility_stress");
    expect(filtered.runs.length).toBeGreaterThan(0);
    expect(filtered.runs.every(
      (r: { scenario_type: string }) => r.scenario_type === "volatility_stress")).toBe(true);
    const all = await (await page.request.get(`${API}/export`)).json();
    expect(all.total_matching_runs).toBeGreaterThan(filtered.total_matching_runs);
    assertNoFailedLocalRequests(failures);
  });

  test("scenario definition, execution order and deferred factor shocks are visible", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Flagship combined stress on the ERC book/);
    await expect(page.getByTestId("stress-scenario-definition")).toBeVisible();
    await expect(page.getByText(/Documented execution order/)).toBeVisible();
    await expect(page.getByText(/Factor shocks are deferred in v1/)).toBeVisible();
    await expect(page.getByText(/Absolute price shocks are unsupported/)).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("detail pages stay clean across demo cases", async ({ page }) => {
    await seedDemo(page);
    for (const name of [/Historical window replay/, /Single-asset shock/,
                        /Additive volatility shock/] as RegExp[]) {
      await openDetail(page, name);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
      await assertNoHorizontalOverflow(page);
      const body = await page.locator("body").innerText();
      expect(body).not.toMatch(BANNED_WORDING);
      await page.getByRole("button", { name: "← Back to runs" }).click();
    }
    assertNoFailedLocalRequests(failures);
  });
});
