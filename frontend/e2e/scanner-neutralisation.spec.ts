import { expect, test } from "@playwright/test";
import { isolationHeader, verifyStrategyEnsembleIsolation } from "./strategyEnsembleIsolation";

test("Scanner policies, actual validation, unavailable beta, explicit download and viewports", async ({ page, request, baseURL }) => {
  const token = process.env.E2E_STRATEGY_ENSEMBLE_TOKEN;
  await verifyStrategyEnsembleIsolation(baseURL, token, (url, options) => request.get(url, options));
  await page.setExtraHTTPHeaders({ [isolationHeader]: token! });
  const computes: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST" && new URL(r.url()).pathname.startsWith("/api/scanner/")) computes.push(r.url()); });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Workspaces" });
  await nav.getByRole("button", { name: "Cross-Sectional Scanner", exact: true }).click();
  await expect(page.getByLabel("Portfolio policy")).toHaveValue("legacy");
  await page.getByRole("button", { name: "Load validation parameters" }).click();
  await expect(page.getByRole("status")).toContainText("Click Run or Validate");
  expect(computes).toEqual([]);
  const run = page.waitForResponse((r) => r.url().endsWith("/api/scanner/backtest"));
  await page.getByRole("button", { name: "Run Scanner", exact: true }).click();
  expect((await run).status()).toBe(200);
  await expect(page.getByRole("table", { name: "Scanner neutralisation stages" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Raw and transformed scanner scores" })).toBeVisible();
  await page.getByRole("button", { name: "Load declared-p fixture" }).click();
  const validated = page.waitForResponse((r) => r.url().endsWith("/api/scanner/validate"));
  await page.getByRole("button", { name: "Validate scanner family" }).click();
  const response = await validated;
  expect(response.status()).toBe(200);
  const actual = await response.json();
  expect(actual.candidates.map((c: { correction: { holm: number } }) => c.correction.holm)).toEqual([.03, .08, .2]);
  expect(actual.folds.every((f: { audit: { valid: boolean } }) => f.audit.valid)).toBe(true);
  await expect(page.getByRole("table", { name: "Scanner candidate corrections" })).toContainText("beta: unavailable");
  await expect(page.getByTestId("scanner-validation-results")).toContainText("Synthetic universe");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download validation JSON" }).click();
  expect((await download).suggestedFilename()).toMatch(/^quantlab-scanner-validation-[a-f0-9]{12}\.json$/);
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  const before = computes.length;
  await page.getByLabel("Embargo (calendar days)").fill("2");
  await expect(page.getByTestId("scanner-validation-results")).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 900 });
  await nav.getByRole("button", { name: "Home", exact: true }).click();
  await nav.getByRole("button", { name: "Cross-Sectional Scanner", exact: true }).click();
  expect(computes).toHaveLength(before);
});
