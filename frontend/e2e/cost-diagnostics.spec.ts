/**
 * Cost Diagnostics Lab E2E coverage (Phase 55.0).
 *
 * Isolation policy (docs/COST_DIAGNOSTICS_RUNBOOK.md): the only writes are
 * the idempotent demo seeds (unique demo_key; they cascade through every
 * other registry's idempotent demo loader) plus one deliberate baseline
 * marking on a demo run — real user records are never modified.  No
 * external network.
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

const HEADER = /Transaction Cost, Slippage & Capacity Diagnostics Lab/;

const BANNED_WORDING =
  /optimal scenario|optimal scale|optimal capital|recommended size|recommended broker|scalable strategy|guaranteed capacity|guaranteed impact|profitable after costs|zero slippage|realistic fill|institutional-grade|best broker|safe strategy/i;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Complete gross-to-net/ }),
  ).toBeVisible({ timeout: 90_000 });
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

test.describe("cost diagnostics lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Cost & Capacity", HEADER);
  });

  test("opens with explicit-assumption and no-execution disclaimers", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/no order execution/i).first()).toBeVisible();
    await expect(page.getByText(/never zero/i).first()).toBeVisible();
    await expect(page.getByText(/no-look-ahead policy/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /High turnover erosion/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Regime-linked period costs/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow by completeness status", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Completeness", { exact: true }).selectOption("partial");
    await expect(page.getByRole("button", { name: /Partial inputs/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /High turnover erosion/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /High turnover erosion/ })).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("complete run: waterfall reconciles components to total and net", async ({ page }) => {
    await seedDemo(page);
    // exact numeric reconciliation via the API the page itself uses
    const listing = await (await page.request.get(
      "/api/cost-diagnostics/runs?query=Complete+gross-to-net")).json();
    const run = await (await page.request.get(
      `/api/cost-diagnostics/runs/${listing.items[0].id}`)).json();
    const totals = run.aggregates.component_totals;
    const sum = (["commission", "spread", "slippage", "impact"] as const)
      .map((c) => totals[c] ?? 0)
      .reduce((a: number, b: number) => a + b, 0);
    expect(Math.abs(sum - run.aggregates.total_cost)).toBeLessThan(1e-9);
    expect(Math.abs(run.aggregates.gross_total - run.aggregates.total_cost
      - run.aggregates.net_total)).toBeLessThan(1e-9);

    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByRole("heading", { name: "Gross-to-net waterfall" })).toBeVisible();
    await expect(page.getByText("Gross result").first()).toBeVisible();
    await expect(page.getByText("Net result").first()).toBeVisible();
    await expect(page.getByText(/never treated as zero/i).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Cost composition" })).toBeVisible();
    await expect(page.getByText("Total estimated cost").first()).toBeVisible();
    await expect(page.getByText(/Market impact/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("partial-input run keeps missing spread/ADV unavailable, not zero", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Partial inputs/ }).click();
    await expect(page.getByText("Partial", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/miss cost inputs/).first()).toBeVisible();
    await expect(page.getByText(/not zero-filled/).first()).toBeVisible();
    // per-observation table lists the missing components by name
    await expect(page.getByRole("heading", { name: "Per-observation reconciliation" })).toBeVisible();
    await expect(page.locator("td", { hasText: "spread, impact" }).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("high-turnover run shows gross-positive becoming net-nonpositive", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /High turnover erosion/ }).click();
    const row = page.locator("div", { hasText: /^Gross-positive becoming net-nonpositive/ }).last();
    await expect(row).toBeVisible();
    const value = await row.locator("span").last().textContent();
    expect(Number.parseInt(value ?? "0", 10)).toBeGreaterThanOrEqual(10);
    // neutral wording — these are not called failed trades
    await expect(page.getByText(/failed trades/i)).toHaveCount(0);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("sensitivity grid marks the base scenario and names none optimal", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByRole("heading", { name: /Cost-sensitivity scenarios/ })).toBeVisible();
    await expect(page.getByText("base scenario").first()).toBeVisible();
    const body = (await page.locator("main").innerText()).toLowerCase();
    expect(body).not.toMatch(BANNED_WORDING);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("capacity curve: participation rises with scale, fees behave by unit", async ({ page }) => {
    await seedDemo(page);
    const listing = await (await page.request.get(
      "/api/cost-diagnostics/runs?query=Complete+gross-to-net")).json();
    const cap = await (await page.request.get(
      `/api/cost-diagnostics/runs/${listing.items[0].id}/capacity`)).json();
    const parts = cap.items.map((r: { max_participation: number }) => r.max_participation);
    for (let i = 1; i < parts.length; i += 1) expect(parts[i]).toBeGreaterThan(parts[i - 1]);

    // fixed per-order fees stay fixed while per-contract slippage scales
    const fixedListing = await (await page.request.get(
      "/api/cost-diagnostics/runs?query=Fixed+per-order")).json();
    const fixedCap = await (await page.request.get(
      `/api/cost-diagnostics/runs/${fixedListing.items[0].id}/capacity`)).json();
    const byScale = new Map(fixedCap.items.map(
      (r: { scale: number }) => [r.scale, r] as const));
    const s1 = byScale.get(1) as { commission_total: number; slippage_total: number };
    const s5 = byScale.get(5) as { commission_total: number; slippage_total: number };
    expect(s5.commission_total).toBeCloseTo(s1.commission_total, 6);
    expect(s5.slippage_total).toBeCloseTo(5 * s1.slippage_total, 6);

    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByRole("heading", { name: /Capacity scaling/ })).toBeVisible();
    await expect(page.getByText(/never historical prices/).first()).toBeVisible();
    await expect(page.getByText(/executable capacity/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("participation-threshold warning is visible on the flagship run", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByText(/exceed the configured participation threshold/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("regime-linked run conditions costs on stored assignments", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Regime-linked period costs/ }).click();
    await expect(page.getByRole("heading", { name: "Costs by stored regime assignment" })).toBeVisible();
    await expect(page.getByText(/never recomputed/).first()).toBeVisible();
    const table = page.locator("table", { hasText: "Regime" }).last();
    await expect(table.locator("td", { hasText: "high" }).first()).toBeVisible();
    await expect(table.locator("td", { hasText: "low" }).first()).toBeVisible();
    await expect(page.getByText(/no regime is\s+cheapest|No regime is/i).first()).toBeVisible();
    // verified causal inputs on this run
    await expect(page.getByText("Verified causal inputs").first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("invalid future-looking run cannot become a baseline", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Invalid future-looking ADV input/ }).click();
    await expect(page.getByText("Invalid", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/looks ahead/).first()).toBeVisible();
    await page.getByRole("button", { name: "Mark as scope baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 15_000 });
    // the deliberate 409 is the only failed request in this test
    const unexpected = failures.filter((f) => !f.url.includes("mark-baseline"));
    assertNoFailedLocalRequests(unexpected);
  });

  test("eligible run can be marked baseline (comparison reference only)", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /High turnover erosion/ }).click();
    const markButton = page.getByRole("button", { name: "Mark as scope baseline" });
    if (await markButton.count()) {
      await markButton.click();
      await expect(page.getByText("Baseline marked")).toBeVisible({ timeout: 15_000 });
    }
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    await expect(page.getByText(/never a sizing or execution recommendation/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    const rows = page.locator("tbody tr");
    await rows.filter({ hasText: "Complete gross-to-net" }).first()
      .locator("input[type=checkbox]").check();
    await rows.filter({ hasText: "High turnover erosion" }).first()
      .locator("input[type=checkbox]").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByRole("heading", { name: "Compare cost-diagnostic runs" })).toBeVisible();
    await expect(page.getByText(/universes differ|assumptions differ/).first()).toBeVisible();
    await expect(page.getByText(/neither run is labelled cheaper, better, or recommended/)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("export downloads JSON without paths or credentials", async ({ page }) => {
    await seedDemo(page);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/quantlab-cost-diagnostics-.*\.json/);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(chunk as Buffer);
    const text = Buffer.concat(chunks).toString("utf-8");
    expect(text).toContain("cost_diagnostics_export_v1");
    expect(text).not.toMatch(/C:\\\\|C:\/Users|\/home\/|api[_-]?key|secret|password/i);
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
    await expect(page.getByText("Export ready")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls are dark with readable units in the detail view", async ({ page }) => {
    await seedDemo(page);
    await expectDarkBackground(page.getByLabel("Status", { exact: true }));
    await expectDarkBackground(page.getByLabel("Integrity", { exact: true }));
    await expectDarkBackground(page.getByLabel("Completeness", { exact: true }));
    await expectDarkBackground(page.getByLabel("Search", { exact: true }));
    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    // units are explicit beside values
    await expect(page.getByText(/bps of traded notional/).first()).toBeVisible();
    await expect(page.getByText(/USD/).first()).toBeVisible();
    await expect(page.getByText(/not annualized/).first()).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("runs table and detail fit at desktop without column overlap", async ({ page }) => {
    await seedDemo(page);
    await assertNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByRole("heading", { name: "Gross-to-net waterfall" })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("stays usable at 1024 and 768 widths", async ({ page }) => {
    await seedDemo(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await assertNoHorizontalOverflow(page);
    await page.getByRole("button", { name: /Regime-linked period costs/ }).click();
    await expect(page.getByRole("heading", { name: "Costs by stored regime assignment" })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 900 });
    await assertNoHorizontalOverflow(page);
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no banned overclaim wording anywhere in the lab", async ({ page }) => {
    await seedDemo(page);
    const listBody = (await page.locator("main").innerText()).toLowerCase();
    expect(listBody).not.toMatch(BANNED_WORDING);
    await page.getByRole("button", { name: /Complete gross-to-net/ }).click();
    await expect(page.getByRole("heading", { name: "Gross-to-net waterfall" })).toBeVisible();
    const detailBody = (await page.locator("main").innerText()).toLowerCase();
    expect(detailBody).not.toMatch(BANNED_WORDING);
    assertNoFailedLocalRequests(failures);
  });
});
