import { expect, test } from "@playwright/test";
import { isolationHeader, verifyStrategyEnsembleIsolation } from "./strategyEnsembleIsolation";
import type { ScannerValidationResponse } from "../src/lib/scannerAdvanced";

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
  await expect(page.getByRole("status").filter({ hasText: "Validation parameters loaded" })).toContainText("Click Run or Validate");
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
  const actual: ScannerValidationResponse = await response.json();
  expect(actual.candidates.map((c) => c.candidate_id)).toEqual(["dollar", "sector", "beta"]);
  expect(actual.candidates.map((c) => c.status)).toEqual(["available", "available", "unavailable"]);
  expect(actual.candidates.map((c) => c.correction.raw_p_value)).toEqual([.01, .04, .2]);
  actual.candidates.forEach((candidate, index) => {
    expect(candidate.correction.bonferroni).toBeCloseTo([.03, .12, .6][index], 12);
  });
  expect(actual.candidates.map((c) => c.correction.holm)).toEqual([.03, .08, .2]);
  expect(actual.folds).toHaveLength(3);
  for (const fold of actual.folds) {
    expect(fold.test_ids.length).toBeGreaterThan(0);
    expect(fold.audit.valid).toBe(true);
    expect(fold.audit.remaining_overlap_count).toBe(0);
  }
  const corrections = page.getByRole("table", { name: "Scanner candidate corrections" });
  for (const [candidate, raw, bonferroni, holm] of [
    ["dollar", "0.0100", "0.0300", "0.0300"],
    ["sector", "0.0400", "0.1200", "0.0800"],
    ["beta", "0.2000", "0.6000", "0.2000"],
  ]) {
    const row = corrections.getByRole("row").filter({ has: page.getByRole("cell", { name: new RegExp(`^${candidate}:`) }) });
    await expect(row).toHaveCount(1);
    await expect(row.getByRole("cell").nth(2)).toHaveText(raw);
    await expect(row.getByRole("cell").nth(3)).toHaveText(bonferroni);
    await expect(row.getByRole("cell").nth(4)).toHaveText(holm);
    await expect(row.getByRole("cell").nth(6)).toHaveText("declared");
  }
  await expect(corrections).toContainText("beta: unavailable");
  expect(actual.candidates[2].outcomes).toEqual([]);
  const results = page.getByTestId("scanner-validation-results");
  await expect(results).toContainText("Synthetic universe");
  await expect(results).toContainText("PBO: no scanner CSCV/selection trial contract; purged folds are not PBO");
  await expect(results).toContainText("DSR: trial population and selection assumptions are not established");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download validation JSON" }).click();
  const completedDownload = await download;
  expect(completedDownload.suggestedFilename()).toBe(`quantlab-scanner-validation-${actual.result_fingerprint.slice(0, 12)}.json`);
  const stream = await completedDownload.createReadStream();
  if (!stream) throw new Error("Completed scanner download has no readable contents");
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString("utf8"))).toEqual(actual);
  expect(computes).toHaveLength(2);
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  const before = computes.length;
  await page.getByLabel("Embargo (calendar days)").fill("2");
  await expect(page.getByTestId("scanner-validation-results")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download validation JSON" })).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 900 });
  await nav.getByRole("button", { name: "Home", exact: true }).click();
  await nav.getByRole("button", { name: "Cross-Sectional Scanner", exact: true }).click();
  expect(computes).toHaveLength(before);
});
