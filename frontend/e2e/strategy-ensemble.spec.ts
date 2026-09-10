/** Phase 64 workflow tests. Requires already-running, explicitly isolated services.
 * Never starts services, deletes a database or writes frozen screenshots. */
import { expect, test, type Page } from "@playwright/test";
import { assertNoHorizontalOverflow, expectNoRawStackTrace, expectNoVisibleNaNOrInfinity } from "./helpers";

const API = "/api/strategy-ensembles";
async function open(page: Page, name: string) {
  await page.getByRole("button", { name, exact: true }).click();
  await expect(page.getByTestId("strategy-ensemble-detail")).toBeVisible();
}
async function detail(page: Page, name: string) {
  const listing = await (await page.request.get(`${API}/runs?page_size=100`)).json();
  const row = listing.items.find((r: { name: string }) => r.name === name);
  expect(row).toBeTruthy();
  return (await page.request.get(`${API}/runs/${row.id}`)).json();
}

test.describe("strategy ensemble lab", () => {
  test.skip(process.env.E2E_STRATEGY_ENSEMBLE_ISOLATED !== "1",
    "Set E2E_STRATEGY_ENSEMBLE_ISOLATED=1 only after verifying the backend uses a disposable database.");
  test.beforeEach(async ({ page, baseURL }) => {
    expect(["localhost", "127.0.0.1", "[::1]"]).toContain(new URL(baseURL!).hostname);
    await page.goto("/?view=strategyensemble");
    await expect(page.getByTestId("strategy-ensemble-panel")).toBeVisible();
    await expect(page.getByRole("button", { name: "Load demo runs" })).toBeEnabled();
    await page.getByRole("button", { name: "Load demo runs" }).click();
    await expect(page.getByText(/demo runs created; .* already present/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Identical streams", exact: true })).toBeVisible();
  });
  test("permalink, sidebar and back navigation", async ({ page }) => {
    await page.getByRole("button", { name: "Home", exact: true }).first().click();
    await page.goBack();
    await expect(page.getByTestId("strategy-ensemble-panel")).toBeVisible();
  });
  test("demo loader is idempotent", async ({ page }) => {
    const first = await (await page.request.post(`${API}/demo-seed`)).json();
    const second = await (await page.request.post(`${API}/demo-seed`)).json();
    expect(first.created_count).toBe(0);
    expect(second.run_ids).toEqual(first.run_ids);
  });
  test("identical streams and common-sample matrix", async ({ page }) => {
    await open(page, "Identical streams");
    await expect(page.getByRole("table", { name: "pearson matrix: strict common sample (N=40)" })).toBeVisible();
    const r = await detail(page, "Identical streams");
    expect(r.results.matrix.effective_strategy_count).toBeCloseTo(1);
  });
  test("inverse returns remain a descriptive combination", async ({ page }) => {
    await open(page, "Inverse streams");
    const r = await detail(page, "Inverse streams");
    expect(r.results.ensemble.drawdown.compounded_return).toBe(0);
  });
  test("constant correlation is unavailable", async ({ page }) => {
    await open(page, "Constant stream");
    await expect(page.getByText(/Matrix unavailable:/)).toBeVisible();
  });
  test("missing periods expose pair-specific overlap", async ({ page }) => {
    await open(page, "Missing periods");
    await expect(page.getByRole("table", { name: "Exact alignment and missingness" })).toBeVisible();
    const r = await detail(page, "Missing periods");
    expect(r.results.pairwise[0].n).toBeGreaterThan(r.results.ensemble.n);
  });
  test("tail loss overlap retains real counts", async ({ page }) => {
    await open(page, "Joint losses and dissimilar gains");
    const r = await detail(page, "Joint losses and dissimilar gains");
    expect(r.results.pairwise[0].simultaneous_loss_count).toBe(10);
    await expect(page.getByRole("table", { name: /Pairwise similarity/ })).toBeVisible();
  });
  test("equal weights and contributions reconcile", async ({ page }) => {
    await open(page, "Identical streams");
    const r = await detail(page, "Identical streams");
    expect(r.results.ensemble.weights.effective).toEqual({ a: .5, b: .5 });
    expect(r.results.ensemble.reconciliation_max_residual).toBe(0);
    await expect(page.getByRole("table", { name: "Contribution summary" })).toBeVisible();
  });
  test("drawdowns include the first loss", async ({ page }) => {
    await open(page, "Identical streams");
    const r = await detail(page, "Identical streams");
    expect(r.results.ensemble.drawdown.periods[0].drawdown).toBeCloseTo(-.02);
    await expect(page.getByRole("table", { name: "Ensemble period reconciliation and drawdown" })).toBeVisible();
  });
  test("net costs are not deducted twice", async ({ page }) => {
    await open(page, "Net costs already included");
    const r = await detail(page, "Net costs already included");
    expect(r.results.ensemble.periods[0].ensemble_return).toBe(-.02);
    expect(r.results.ensemble.costs.underlying_cost_deducted_again).toBe(false);
    await expect(page.getByRole("table", { name: "Cost basis and turnover" })).toContainText("net_of_strategy_costs");
  });
  test("stored regimes display counts and no automatic switching", async ({ page }) => {
    await open(page, "Stored regimes and held-out");
    await expect(page.getByRole("table", { name: "Stored regime observations" })).toContainText("first");
    const r = await detail(page, "Stored regimes and held-out");
    expect(r.results.regimes.map((g: { n: number }) => g.n)).toEqual([20, 20]);
  });
  test("held-out uses frozen weights", async ({ page }) => {
    await open(page, "Stored regimes and held-out");
    await expect(page.getByRole("table", { name: "Training and held-out (frozen weights)" })).toBeVisible();
    const r = await detail(page, "Stored regimes and held-out");
    expect(r.results.validation.training.weights).toEqual(r.results.validation.held_out.weights);
  });
  test("explicit sensitivity scenarios have no winner", async ({ page }) => {
    await open(page, "Static weights and sensitivity");
    await expect(page.getByRole("table", { name: "Explicit weight sensitivity" })).toContainText("Explicit 25/75");
  });
  test("baseline is an explicit lifecycle action", async ({ page }) => {
    await open(page, "Identical streams");
    await page.getByRole("button", { name: "Mark baseline" }).click();
    await expect(page.getByText("Comparison baseline updated.")).toBeVisible();
  });
  test("invalid timing cannot be a baseline", async ({ page }) => {
    await page.getByRole("button", { name: "Invalid outcome timing", exact: true }).click();
    await expect(page.getByRole("button", { name: "Mark baseline" })).toBeDisabled();
    await expect(page.getByText(/timing violation:/)).toBeVisible();
  });
  test("neutral comparison", async ({ page }) => {
    await page.getByRole("checkbox", { name: "Compare Identical streams", exact: true }).check();
    await page.getByRole("checkbox", { name: "Compare Inverse streams", exact: true }).check();
    await page.getByRole("button", { name: "Compare runs", exact: true }).click();
    await expect(page.getByRole("table", { name: "Neutral run comparison" })).toBeVisible();
  });
  test("JSON download matches the persisted result", async ({ page }) => {
    await open(page, "Identical streams");
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toMatch(/^quantlab-strategy-ensemble-\d+\.json$/);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
    const body = JSON.parse(Buffer.concat(chunks).toString());
    const r = await detail(page, "Identical streams");
    expect(body.fingerprints).toEqual(r.fingerprints);
    expect(body.results.ensemble).toEqual(r.results.ensemble);
  });
  test("no nonfinite values, raw stack traces or allocation claims", async ({ page }) => {
    await open(page, "Identical streams");
    await expectNoRawStackTrace(page);
    await expectNoVisibleNaNOrInfinity(page);
    expect(await page.getByTestId("strategy-ensemble-panel").innerText()).not.toMatch(/optimal ensemble|best strategy mix|recommended allocation|proven alpha/i);
  });
  test("dark editable controls", async ({ page }) => {
    await page.getByText("Create supplied return-stream run").click();
    const field = page.getByLabel("Run definition (JSON)");
    await field.fill("{}");
    await field.fill("");
    await expect(field).toHaveValue("");
    const color = await field.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(color).not.toBe("rgb(255, 255, 255)");
  });
  for (const width of [1024, 768]) {
    test(`bounded ${width}px layout`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await open(page, "Identical streams");
      await assertNoHorizontalOverflow(page);
    });
  }
});
