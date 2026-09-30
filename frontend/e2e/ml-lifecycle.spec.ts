import { test, expect, type Page } from "@playwright/test";
import { verifyMLLifecycleIsolation } from "./mlLifecycleIsolation";
import { isolationHeader } from "./strategyEnsembleIsolation";

async function checkViewports(page: Page) {
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  }
}

test("ML lifecycle: explicit demo, pinned provenance, refusal, export and responsive navigation", async ({ page, request, baseURL }) => {
  const token = process.env.E2E_STRATEGY_ENSEMBLE_TOKEN;
  await verifyMLLifecycleIsolation(baseURL, token, (url, options) => request.get(url, options));
  await page.setExtraHTTPHeaders({ [isolationHeader]: token! });
  const mutations: string[] = [];
  page.on("request", (event) => {
    if (new URL(event.url()).pathname.startsWith("/api/ml-lifecycles") && event.method() === "POST") mutations.push(event.url());
  });
  await page.goto("/?view=mllifecycle");
  await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
  const sidebar = page.getByRole("navigation", { name: "Workspaces" });
  await sidebar.getByRole("button", { name: "Home", exact: true }).click();
  await expect(page.getByTestId("ml-lifecycle-panel")).not.toBeVisible();
  await expect(page).not.toHaveURL(/view=mllifecycle/);
  await page.goBack();
  await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
  await expect(page).toHaveURL(/view=mllifecycle/);
  await page.goForward();
  await expect(page.getByTestId("ml-lifecycle-panel")).not.toBeVisible();
  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette).toBeVisible();
  await palette.getByRole("textbox").fill("Open ML Research Lifecycle");
  await palette.getByText("Open ML Research Lifecycle", { exact: true }).click();
  await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
  await expect(page).toHaveURL(/view=mllifecycle/);
  await page.getByLabel("Completeness", { exact: true }).selectOption("incomplete");
  await expect(page.getByText("No matching ML lifecycles")).toBeVisible();
  await checkViewports(page);
  await page.getByLabel("Completeness", { exact: true }).selectOption("");
  expect(mutations).toEqual([]);
  await page.getByRole("button", { name: "Create / resume synthetic demo" }).click();
  await expect(page.getByText("Synthetic lifecycle completed.", { exact: true })).toBeVisible({ timeout: 120_000 });
  const modelTable = page.getByRole("table", { name: "Fitted models" });
  await expect(modelTable).toBeVisible();
  await expect(modelTable.locator("tbody tr")).toHaveCount(5);
  await expect(page.getByRole("table", { name: "Frozen calibration" })).toContainText("Inner OOF");
  await expect(page.getByRole("table", { name: "Prediction provenance" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Diagnostic links" }).locator("tbody tr")).toHaveCount(5);
  await page.getByRole("button", { name: "Inspect validation record" }).click();
  await expect(page.getByTestId("ml-linked-detail")).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toMatch(/^quantlab-ml-lifecycle-\d+\.json$/);
  const stream = await download.createReadStream();
  expect(stream).not.toBeNull();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const text = Buffer.concat(chunks).toString("utf8");
  const exported = JSON.parse(text);
  expect(exported.schema_version).toBe(1);
  expect(exported.type).toBe("quantlab_ml_lifecycle");
  expect(exported.lifecycle.integrity).toBe("intact");
  expect(exported.lifecycle.completeness).toBe("complete");
  expect(exported.lifecycle.snapshot.models).toHaveLength(5);
  expect(exported.lifecycle.snapshot.predictions.filter((p: { role: string }) => p.role === "held_out")).toHaveLength(32);
  expect(text).not.toContain(token!);
  expect(text).not.toMatch(/[A-Z]:\\|\/Users\/|\/home\/|\bNaN\b|\bInfinity\b/);
  await checkViewports(page);
  const id = exported.lifecycle.id;
  // The single demo is intentionally idempotent. API self-comparison is real;
  // two-record UI selection is covered by the component regression.
  const comparison = await request.get(`${baseURL}/api/ml-lifecycles/compare?a=${id}&b=${id}`, { headers: { [isolationHeader]: token! } });
  expect(comparison.status()).toBe(200);
  const compared = await comparison.json();
  expect(compared.note).toContain("no ranking");
  expect(compared.rows.find((row: { field: string }) => row.field === "identities")).toMatchObject({ a: exported.lifecycle.identities, b: exported.lifecycle.identities });
  expect(compared.metrics[0]).toEqual(compared.metrics[1]);
  const refused = await request.post(`${baseURL}/api/ml-lifecycles`, { headers: { [isolationHeader]: token! }, data: { source_root: "not-an-api-path" } });
  expect(refused.status()).toBe(422);
  await page.getByRole("button", { name: "Open validation lab" }).click();
  await expect(page.getByTestId("ml-lifecycle-panel")).not.toBeVisible();
  await expect(page).not.toHaveURL(/view=mllifecycle/);
  await sidebar.getByRole("button", { name: "ML Research Lifecycle", exact: true }).click();
  await expect(page.getByTestId("ml-lifecycle-panel")).toBeVisible();
  await expect(page).toHaveURL(/view=mllifecycle/);
  expect(mutations).toHaveLength(1);
});
