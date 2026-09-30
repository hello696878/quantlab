import { test, expect } from "@playwright/test";
import { verifyMLLifecycleIsolation } from "./mlLifecycleIsolation";
import { isolationHeader } from "./strategyEnsembleIsolation";

test("ML lifecycle: explicit demo, pinned provenance, refusal, export and responsive navigation", async ({ page, request, baseURL }) => {
  const token = process.env.E2E_STRATEGY_ENSEMBLE_TOKEN;
  await verifyMLLifecycleIsolation(baseURL, token, (url, options) => request.get(url, options));
  await page.setExtraHTTPHeaders({ [isolationHeader]: token! });
  await page.goto("/?view=mllifecycle");
  await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
  await page.getByLabel("Completeness", { exact: true }).selectOption("incomplete");
  await expect(page.getByText("No matching ML lifecycles")).toBeVisible();
  await page.getByLabel("Completeness", { exact: true }).selectOption("");
  await page.getByRole("button", { name: "Create / resume synthetic demo" }).click();
  await expect(page.getByText("Synthetic lifecycle completed.", { exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("table", { name: "Fitted models" })).toBeVisible();
  await page.getByRole("button", { name: "Inspect validation record" }).click();
  await expect(page.getByTestId("ml-linked-detail")).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/^quantlab-ml-lifecycle-\d+\.json$/);
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  }
  const listing = await request.get(`${baseURL}/api/ml-lifecycles`, { headers: { [isolationHeader]: token! } });
  const id = (await listing.json()).items[0].id;
  const comparison = await request.get(`${baseURL}/api/ml-lifecycles/compare?a=${id}&b=${id}`, { headers: { [isolationHeader]: token! } });
  expect((await comparison.json()).note).toContain("no ranking");
  const refused = await request.post(`${baseURL}/api/ml-lifecycles`, { headers: { [isolationHeader]: token! }, data: { source_root: "not-an-api-path" } });
  expect(refused.status()).toBe(422);
  await page.getByRole("button", { name: "Open validation lab" }).click();
  await expect(page.getByTestId("ml-lifecycle-panel")).not.toBeVisible();
});
