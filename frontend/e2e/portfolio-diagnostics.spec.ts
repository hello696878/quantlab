/**
 * Portfolio Diagnostics Lab E2E coverage (Phase 56.0).
 *
 * Isolation policy (docs/PORTFOLIO_DIAGNOSTICS_RUNBOOK.md): the only writes
 * are the idempotent demo seeds (unique demo_key; they cascade through every
 * other registry's idempotent demo loader) plus one deliberately rejected
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

const HEADER = /Portfolio Construction & Risk Budgeting Diagnostics Lab/;

const BANNED_WORDING =
  /the optimal portfolio|is optimal|safest choice|we recommend|recommended allocation:|guaranteed diversification|guaranteed risk reduction|production-ready portfolio|profitable allocation|ideal weights|institutional-grade|risk-free portfolio|zero risk/i;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Equal risk contribution \(ERC\)/ }),
  ).toBeVisible({ timeout: 120_000 });
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

test.describe("portfolio diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Portfolio Diagnostics", HEADER);
  });

  test("opens with the no-look-ahead and no-allocation disclaimers", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/no-look-ahead policy|no look-ahead/i).first()).toBeVisible();
    await expect(page.getByText(/recommends an allocation/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Inverse-volatility weighting/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: /Equal-weight reference/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by method", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Method", { exact: true }).selectOption("erc");
    await expect(page.getByRole("button", { name: /Equal risk contribution/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Inverse-volatility weighting/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Inverse-volatility weighting/ })).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("equal-weight reference: weights sum to the configured normalization", async ({ page }) => {
    await seedDemo(page);
    const listing = await (await page.request.get(
      "/api/portfolio-diagnostics/runs?query=Equal-weight+reference")).json();
    const weights = await (await page.request.get(
      `/api/portfolio-diagnostics/runs/${listing.items[0].id}/weights`)).json();
    const total = weights.items.reduce(
      (a: number, w: { weight: number }) => a + w.weight, 0);
    expect(Math.abs(total - 1.0)).toBeLessThan(1e-9);

    await page.getByRole("button", { name: /Equal-weight reference/ }).click();
    await expect(page.getByRole("heading", { name: "Weight allocation" })).toBeVisible();
    await expect(page.getByText(/of portfolio/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("inverse-volatility: lower-volatility assets carry higher weights", async ({ page }) => {
    await seedDemo(page);
    const listing = await (await page.request.get(
      "/api/portfolio-diagnostics/runs?query=Inverse-volatility")).json();
    const weights = await (await page.request.get(
      `/api/portfolio-diagnostics/runs/${listing.items[0].id}/weights`)).json();
    const byId = new Map<string, number>(weights.items.map(
      (w: { asset_id: string; weight: number }) =>
        [w.asset_id, w.weight] as const));
    expect(byId.get("lowvol-a")!).toBeGreaterThan(byId.get("midvol-a")!);
    expect(byId.get("midvol-a")!).toBeGreaterThan(byId.get("highvol-b")!);
    await page.getByRole("button", { name: /Inverse-volatility weighting/ }).click();
    await expect(page.getByRole("heading", { name: "Weight allocation" })).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("ERC: risk contributions reconcile and match targets", async ({ page }) => {
    await seedDemo(page);
    const listing = await (await page.request.get(
      "/api/portfolio-diagnostics/runs?query=Equal+risk+contribution")).json();
    const run = await (await page.request.get(
      `/api/portfolio-diagnostics/runs/${listing.items[0].id}`)).json();
    const pcrSum = run.risk.pcr.reduce((a: number, v: number) => a + v, 0);
    expect(Math.abs(pcrSum - 1.0)).toBeLessThan(1e-7);
    const ccrSum = run.risk.ccr.reduce((a: number, v: number) => a + v, 0);
    expect(Math.abs(ccrSum - run.risk.volatility)).toBeLessThan(1e-8);
    expect(run.max_budget_deviation).toBeLessThan(0.01);

    await page.getByRole("button", { name: /Equal risk contribution \(ERC\)/ }).click();
    await expect(page.getByRole("heading", { name: /Risk contributions/ })).toBeVisible();
    await expect(page.getByText(/Target budget/).first()).toBeVisible();
    await expect(page.getByText(/Measured PCR/).first()).toBeVisible();
    await expect(page.getByText(/reconcile within tolerance/).first()).toBeVisible();
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("correlation matrix renders with printed values", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Highly correlated universe/ }).click();
    await expect(page.getByRole("heading", { name: "Covariance & correlation" })).toBeVisible();
    await expect(page.getByText(/printed in every cell/).first()).toBeVisible();
    await expect(page.getByText(/near-singular|effectively singular|condition number/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("degenerate covariance fails honestly; explicit repair is recorded", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Degenerate covariance/ }).click();
    await expect(page.getByText("solver: failed").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark as scope baseline" })).toHaveCount(0);
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await page.getByRole("button", { name: /Singular covariance — explicit eigenvalue floor/ }).click();
    await expect(page.getByText(/eigenvalue floor 1e-8|eigenvalue floor 0\.00000001/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("weight and group caps are satisfied and shown", async ({ page }) => {
    await seedDemo(page);
    const listing = await (await page.request.get(
      "/api/portfolio-diagnostics/runs?query=Minimum+variance")).json();
    const run = listing.items[0];
    expect(run.constraint_violation_count).toBe(0);
    const weights = await (await page.request.get(
      `/api/portfolio-diagnostics/runs/${run.id}/weights`)).json();
    for (const w of weights.items) expect(w.weight).toBeLessThanOrEqual(0.30 + 1e-6);
    await page.getByRole("button", { name: /Minimum variance with weight and group caps/ }).click();
    await expect(page.getByText(/bounds \[/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("turnover cap violation blocks baseline; rebalances render", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Rebalancing with turnover cap/ }).click();
    await expect(page.getByRole("heading", { name: /Rebalances & turnover/ })).toBeVisible();
    await expect(page.getByText(/drifted pre-trade weight/).first()).toBeVisible();
    await expect(page.getByText(/constraint violation/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark as scope baseline" })).toHaveCount(0);
    assertNoFailedLocalRequests(failures);
  });

  test("linked cost estimates stay honest about unavailable components", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Rebalancing with turnover cap/ }).click();
    await expect(page.getByText(/Est\. cost \(return\)/).first()).toBeVisible();
    await expect(page.getByText("partial").first()).toBeVisible();
    await expect(page.getByText(/never zero/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("regime-linked characteristics come from stored assignments", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Regime-conditioned portfolio characteristics/ }).click();
    await expect(page.getByRole("heading", { name: "Portfolio characteristics by stored regime" })).toBeVisible();
    await expect(page.getByText(/never recomputed/).first()).toBeVisible();
    const table = page.locator("table", { hasText: "Regime" }).last();
    await expect(table.locator("td", { hasText: "high" }).first()).toBeVisible();
    await expect(table.locator("td", { hasText: "low" }).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("sensitivity scenarios render with a neutral base marker", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Equal risk contribution \(ERC\)/ }).click();
    await expect(page.getByRole("heading", { name: /Sensitivity scenarios/ })).toBeVisible();
    await expect(page.getByText("base scenario").first()).toBeVisible();
    const body = (await page.locator("main").innerText());
    expect(body).not.toMatch(BANNED_WORDING);
    assertNoFailedLocalRequests(failures);
  });

  test("integrity states: full-sample warned, future-looking invalid", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Full-sample descriptive estimation/ }).click();
    await expect(page.getByText("Full-sample descriptive").first()).toBeVisible();
    await expect(page.getByText(/never leakage-safe/).first()).toBeVisible();
    await page.getByRole("button", { name: "← Back to runs" }).click();
    await page.getByRole("button", { name: /Invalid future-looking weight provenance/ }).click();
    await expect(page.getByText("Invalid", { exact: true }).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    const rows = page.locator("tbody tr");
    await rows.filter({ hasText: "Equal-weight reference" }).first()
      .locator("input[type=checkbox]").check();
    await rows.filter({ hasText: "Inverse-volatility weighting" }).first()
      .locator("input[type=checkbox]").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByRole("heading", { name: "Compare portfolio-diagnostic runs" })).toBeVisible();
    await expect(page.getByText(/methods differ|universes differ/).first()).toBeVisible();
    await expect(page.getByText(/no run is declared a winner/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("export downloads JSON without paths or credentials", async ({ page }) => {
    await seedDemo(page);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/quantlab-portfolio-diagnostics-.*\.json/);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(chunk as Buffer);
    const text = Buffer.concat(chunks).toString("utf-8");
    expect(text).toContain("portfolio_diagnostics_export_v1");
    expect(text).not.toMatch(/C:\\\\|C:\/Users|\/home\/|api[_-]?key|secret|password/i);
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
    await expect(page.getByText("Export ready")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls are dark with visible units in the detail", async ({ page }) => {
    await seedDemo(page);
    await expectDarkBackground(page.getByLabel("Status", { exact: true }));
    await expectDarkBackground(page.getByLabel("Integrity", { exact: true }));
    await expectDarkBackground(page.getByLabel("Method", { exact: true }));
    await expectDarkBackground(page.getByLabel("Search", { exact: true }));
    await page.getByRole("button", { name: /Equal risk contribution \(ERC\)/ }).click();
    await expect(page.getByText(/not annualized/).first()).toBeVisible();
    await expect(page.getByText(/of portfolio/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("desktop, 1024 and 768 stay usable without overlap", async ({ page }) => {
    await seedDemo(page);
    await assertNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Equal risk contribution \(ERC\)/ }).click();
    await expect(page.getByRole("heading", { name: "Weight allocation" })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 900 });
    await assertNoHorizontalOverflow(page);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });
});
