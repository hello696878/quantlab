/**
 * Portfolio Attribution Lab E2E coverage (Phase 58.0).
 *
 * Isolation policy (docs/PORTFOLIO_ATTRIBUTION_RUNBOOK.md): this spec must run
 * against services configured with an isolated test database. It writes the
 * idempotent demo seeds (unique demo_key; cascading through the Phase 56/55
 * demo loaders) and makes one deliberately rejected baseline attempt. It
 * never clears a database and performs no external network access. */

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

const HEADER = /Portfolio Performance Attribution, Benchmark & Active Risk Lab/;

const BANNED_WORDING =
  /prov(?:es|en) alpha|manager skill|demonstrates skill|superior portfolio|best benchmark|recommended portfolio|recommended benchmark|guaranteed performance|GIPS[- ]compliant|certified attribution|profitable allocation|production performance report|institutional-grade attribution|risk-free/i;

const NEGATION =
  /\b(?:not|never|nothing|neither|nor|without|cannot|isn't|does not|doesn't|no)\b/i;

/**
 * The lab's own disclaimers legitimately contain the banned phrases inside
 * NEGATED sentences ("Nothing here proves alpha or manager skill").  Only an
 * AFFIRMATIVE occurrence is a defect, so negated sentences are dropped
 * before matching rather than trying to encode negation in one regex.
 */
function expectNoAffirmativeOverclaim(body: string): void {
  const affirmative = body
    .split(/(?<=[.;:!?])\s+|\n+/)
    .filter((sentence) => !NEGATION.test(sentence))
    .join("\n");
  expect(affirmative).not.toMatch(BANNED_WORDING);
}

const API = "/api/portfolio-attribution";

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Flagship allocation attribution/ }),
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
  await expect(page.getByTestId("portfolio-attribution-detail")).toBeVisible();
}

test.describe("portfolio attribution lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    // seeding cascades several labs' demo loaders on a cold database
    test.setTimeout(240_000);
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Portfolio Attribution", HEADER);
  });

  test("opens with honest-scope disclaimers and no banned wording", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/beginning-of-period weights/i).first()).toBeVisible();
    await expect(page.getByText(/never auto-selected|never selected automatically/i).first()).toBeVisible();
    await expect(page.getByText(/proves alpha or manager skill/i).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expectNoAffirmativeOverclaim(body);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently with 17 documented cases", async ({ page }) => {
    await seedDemo(page);
    const summary = await (await page.request.get(`${API}/summary`)).json();
    expect(summary.runs).toBe(17);
    expect(summary.completed).toBe(17);
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("button", { name: /Flagship allocation attribution/ }),
    ).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by method, linking and integrity", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Method", { exact: true }).selectOption("contribution_only");
    await expect(page.getByRole("button", { name: /Contribution-only attribution/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Flagship allocation attribution/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await page.getByLabel("Linking", { exact: true }).selectOption("carino");
    await expect(page.getByRole("button", { name: /Carino linking/ })).toBeVisible();
    await page.getByRole("button", { name: "Reset filters" }).click();
    await page.getByLabel("Integrity", { exact: true }).selectOption("invalid");
    await expect(page.getByRole("button", { name: /Invalid end-of-period weight timing/ })).toBeVisible();
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Flagship allocation attribution/ })).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("flagship: hand-computed allocation reconciles exactly", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Flagship allocation attribution");
    const periods = await (await page.request.get(`${API}/runs/${id}/periods`)).json();
    const first = periods.items[0];
    // portfolio 1.80%, benchmark 1.50%, active 0.30%, all allocation
    expect(first.portfolio_market_return).toBeCloseTo(0.018, 12);
    expect(first.benchmark_return).toBeCloseTo(0.015, 12);
    expect(first.active_return).toBeCloseTo(0.003, 12);
    expect(first.allocation_effect).toBeCloseTo(0.003, 12);
    expect(first.selection_effect).toBeCloseTo(0, 12);
    expect(first.interaction_effect).toBeCloseTo(0, 12);
    expect(Math.abs(first.residual)).toBeLessThan(1e-9);

    await openDetail(page, /Flagship allocation attribution/);
    await expect(page.getByTestId("attribution-reconciliation")).toBeVisible();
    await expect(page.getByTestId("attribution-brinson")).toBeVisible();
    await expect(page.getByTestId("brinson-chart")).toBeVisible();
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });

  test("asset and group contributions reconcile with the portfolio return", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Flagship allocation attribution");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    const assets = await (await page.request.get(`${API}/runs/${id}/assets`)).json();
    const groups = await (await page.request.get(`${API}/runs/${id}/groups`)).json();
    const assetSum = assets.items.reduce(
      (a: number, r: { arithmetic_contribution: number }) => a + r.arithmetic_contribution, 0);
    const groupSum = groups.items.reduce(
      (a: number, r: { arithmetic_contribution: number }) => a + r.arithmetic_contribution, 0);
    expect(Math.abs(assetSum - run.portfolio_market_return)).toBeLessThan(1e-9);
    expect(Math.abs(groupSum - assetSum)).toBeLessThan(1e-9);
    expect(run.summary.contribution_reconciled).toBe(true);
    expect(run.summary.group_reconciled).toBe(true);

    await openDetail(page, /Flagship allocation attribution/);
    await expect(page.getByTestId("asset-contribution-chart")).toBeVisible();
    await expect(page.getByTestId("attribution-groups")).toContainText("never inferred from asset names");
    await page.getByTestId("attribution-groups").getByRole("button", { name: "Show" }).first().click();
    await expect(page.getByTestId("group-drilldown")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("zero active return: every effect is zero and the ratio is unavailable", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Identical benchmark");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(Math.abs(run.active_return)).toBeLessThan(1e-12);
    expect(Math.abs(run.tracking_error)).toBeLessThan(1e-12);
    expect(run.information_ratio).toBeNull();
    const brinson = await (await page.request.get(`${API}/runs/${id}/brinson`)).json();
    for (const row of brinson.items) {
      expect(Math.abs(row.allocation_effect)).toBeLessThan(1e-9);
      expect(Math.abs(row.selection_effect)).toBeLessThan(1e-9);
      expect(Math.abs(row.interaction_effect)).toBeLessThan(1e-9);
    }
    await openDetail(page, /Identical benchmark/);
    await expect(page.getByTestId("ir-unavailable")).toContainText(/never reported as infinite/);
    assertNoFailedLocalRequests(failures);
  });

  test("selection and interaction effects are separated", async ({ page }) => {
    await seedDemo(page);
    const selId = await runIdByQuery(page, "Within-group selection effect");
    const selPeriods = await (await page.request.get(`${API}/runs/${selId}/periods`)).json();
    expect(selPeriods.items[0].selection_effect).toBeGreaterThan(0);

    const intId = await runIdByQuery(page, "Non-zero interaction effect");
    const intPeriods = await (await page.request.get(`${API}/runs/${intId}/periods`)).json();
    const p = intPeriods.items[0];
    expect(Math.abs(p.interaction_effect)).toBeGreaterThan(1e-9);
    // the three effects plus the residual reproduce the active return
    const explained = p.allocation_effect + p.selection_effect + p.interaction_effect;
    expect(Math.abs(p.active_return - explained - p.residual)).toBeLessThan(1e-12);

    await openDetail(page, /Non-zero interaction effect/);
    await expect(page.getByTestId("attribution-brinson")).toContainText("interaction");
    await expect(page.getByTestId("brinson-residual")).toContainText(/never redistributed/);
    assertNoFailedLocalRequests(failures);
  });

  test("one-sided and zero-weight groups stay honestly unavailable", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Portfolio-only group");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.completeness_status).toBe("partial");
    expect(run.reconciliation_status).toBe("residual");
    const brinson = await (await page.request.get(`${API}/runs/${id}/brinson`)).json();
    const bond = brinson.items.find((r: { group_id: string }) => r.group_id === "bond");
    expect(bond.presence).toBe("portfolio_only");
    await openDetail(page, /Portfolio-only group/);
    await expect(page.getByTestId("attribution-warnings")).toContainText(/portfolio-only assets/);

    await page.getByRole("button", { name: "← Back to runs" }).click();
    await openDetail(page, /Zero group weight on both sides/);
    await expect(page.getByTestId("attribution-brinson")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("benchmark-only asset requires explicit returns and an explicit group", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Benchmark-only group");
    const benchmark = await (await page.request.get(`${API}/runs/${id}/benchmark`)).json();
    expect(benchmark.benchmark.definition.asset_ids).toContain("cm-a");
    expect(benchmark.benchmark.definition.benchmark_only_assets).toContain("cm-a");
    await openDetail(page, /Benchmark-only group/);
    await expect(page.getByTestId("attribution-benchmark")).toContainText(/never selected automatically/);
    await expect(page.getByTestId("attribution-warnings")).toContainText(/benchmark-only assets/);
    assertNoFailedLocalRequests(failures);
  });

  test("arithmetic and Carino linking are labelled distinctly", async ({ page }) => {
    await seedDemo(page);
    const arithId = await runIdByQuery(page, "Arithmetic linking");
    const arith = await (await page.request.get(`${API}/runs/${arithId}`)).json();
    expect(arith.linking.method).toBe("arithmetic");
    expect(Math.abs(arith.linking.linking_residual)).toBeLessThan(1e-9);
    // the arithmetic sum does NOT equal the compounded active return
    expect(Math.abs(arith.linking.arithmetic_vs_geometric_gap)).toBeGreaterThan(1e-9);

    const carinoId = await runIdByQuery(page, "Carino linking");
    const carino = await (await page.request.get(`${API}/runs/${carinoId}`)).json();
    expect(carino.linking.method).toBe("carino");
    expect(carino.linking.available).toBe(true);
    expect(carino.linking.linked_target).toBeCloseTo(
      carino.linking.geometric_active_return, 12);
    expect(Math.abs(carino.linking.linking_residual)).toBeLessThan(1e-9);
    expect(carino.linking.smoothing_factors.length).toBe(carino.period_count);

    await openDetail(page, /Carino linking/);
    await expect(page.getByTestId("attribution-linking")).toContainText(/Carino/);
    await expect(page.getByTestId("attribution-linking")).toContainText(
      /does not generally reconcile/);
    assertNoFailedLocalRequests(failures);
  });

  test("gross versus cost-adjusted keeps costs separate", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Gross versus cost-adjusted");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.cost.total_cost_return).toBeGreaterThan(0);
    expect(run.cost.component_totals.impact).toBeNull();   // honestly missing
    expect(run.portfolio_net_return).toBeCloseTo(
      run.cost.gross_market_return_costed_periods - run.cost.total_cost_return, 12);
    await openDetail(page, /Gross versus cost-adjusted/);
    await expect(page.getByTestId("attribution-cost")).toContainText(/never netted against a narrower cost figure/);
    await expect(page.getByTestId("attribution-cost")).toContainText("unavailable");
    assertNoFailedLocalRequests(failures);
  });

  test("active-risk diagnostics and the unspecified-frequency case", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Flagship allocation attribution");
    const run = await (await page.request.get(`${API}/runs/${id}/active-risk`)).json();
    expect(run.active_risk.tracking_error).toBeGreaterThan(0);
    expect(run.active_risk.annualized_tracking_error).toBeGreaterThan(0);
    expect(run.active_risk.std_convention).toMatch(/sample/);

    const freqId = await runIdByQuery(page, "Unspecified frequency");
    const freq = await (await page.request.get(`${API}/runs/${freqId}`)).json();
    expect(freq.active_risk.tracking_error).toBeGreaterThan(0);
    expect(freq.active_risk.annualized_tracking_error).toBeNull();
    await openDetail(page, /Unspecified frequency/);
    await expect(page.getByTestId("attribution-active-risk")).toContainText(/never assumed/);
    assertNoFailedLocalRequests(failures);
  });

  test("concentration is measured on absolute contributions", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Contribution concentration");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.concentration.herfindahl).toBeGreaterThan(0.5);
    expect(run.concentration.largest_absolute_share).toBeGreaterThan(0.5);
    await openDetail(page, /Contribution concentration/);
    await expect(page.getByTestId("attribution-concentration")).toContainText(
      /not evidence of poor diversification/);
    assertNoFailedLocalRequests(failures);
  });

  test("invalid end-of-period timing is rejected for baseline", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Invalid end-of-period weight timing");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.integrity_status).toBe("invalid");
    const attempt = await page.request.post(`${API}/runs/${id}/mark-baseline`, { data: {} });
    expect(attempt.status()).toBe(409);
    await openDetail(page, /Invalid end-of-period weight timing/);
    await expect(page.getByTestId("attribution-warnings")).toContainText(
      /already embeds that period's return/);
    assertNoFailedLocalRequests(failures);
  });

  test("timeline, policy and the deferred factor decision are visible", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Flagship allocation attribution/);
    await expect(page.getByTestId("attribution-timeline")).toBeVisible();
    await expect(page.getByTestId("attribution-policy")).toBeVisible();
    await expect(page.getByTestId("attribution-policy")).toContainText(
      /Documented execution order/);
    await expect(page.getByTestId("attribution-policy")).toContainText(
      /factor.*deferred in v1|deferred in v1/i);
    await expect(page.getByTestId("attribution-twr")).toContainText(
      /no money-weighted \(IRR\)/);
    assertNoFailedLocalRequests(failures);
  });

  test("compare reports differences neutrally", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("row", { name: /Flagship allocation attribution/ })
      .getByRole("checkbox").check();
    await page.getByRole("row", { name: /Carino linking/ })
      .getByRole("checkbox").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByRole("heading", { name: "Compare attribution runs" })).toBeVisible();
    await expect(page.getByText(/no run is declared better/i)).toBeVisible();
    await expect(page.getByText(/linking/i).first()).toBeVisible();
    const body = await page.locator("body").innerText();
    expectNoAffirmativeOverclaim(body);
    assertNoFailedLocalRequests(failures);
  });

  test("export honours the active filter and is path-free", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Method", { exact: true }).selectOption("contribution_only");
    await expect(page.getByRole("button", { name: /Contribution-only attribution/ })).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/quantlab-portfolio-attribution-.*\.json/);
    await expect(page.getByText(/Export ready/)).toBeVisible();
    const filtered = await (await page.request.get(
      `${API}/export?attribution_method=contribution_only`)).json();
    expect(filtered.filters.attribution_method).toBe("contribution_only");
    expect(filtered.runs.length).toBeGreaterThan(0);
    const text = JSON.stringify(filtered);
    for (const banned of ["C:\\\\", "/home/", "password", "api_key", "secret"]) {
      expect(text).not.toContain(banned);
    }
    const all = await (await page.request.get(`${API}/export`)).json();
    expect(all.total_matching_runs).toBeGreaterThan(filtered.total_matching_runs);
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls use dark theme backgrounds and explicit units", async ({ page }) => {
    await seedDemo(page);
    for (const label of ["Status", "Integrity", "Method", "Linking"]) {
      const control = page.getByLabel(label, { exact: true });
      const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
      const rgb = bg.match(/rgba?\(([^)]+)\)/);
      if (rgb) {
        const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
        expect((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255,
               `${label} background ${bg} should be dark`).toBeLessThan(0.5);
      }
    }
    await openDetail(page, /Flagship allocation attribution/);
    await expect(page.getByText(/per period/).first()).toBeVisible();
    await expect(page.getByText(/%/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("stays usable at 1024 and 768 widths", async ({ page }) => {
    await seedDemo(page);
    for (const width of [1024, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoHorizontalOverflow(page);
      await expectNoVisibleNaNOrInfinity(page);
    }
    await openDetail(page, /Flagship allocation attribution/);
    for (const width of [1024, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoHorizontalOverflow(page);
    }
    assertNoFailedLocalRequests(failures);
  });

  test("detail pages stay clean across demo cases", async ({ page }) => {
    await seedDemo(page);
    for (const name of [/Long\/short book/, /Buy-and-hold benchmark/,
                        /Brinson-Hood-Beebower variant/] as RegExp[]) {
      await openDetail(page, name);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
      await assertNoHorizontalOverflow(page);
      const body = await page.locator("body").innerText();
      expectNoAffirmativeOverclaim(body);
      await page.getByRole("button", { name: "← Back to runs" }).click();
    }
    assertNoFailedLocalRequests(failures);
  });
});
