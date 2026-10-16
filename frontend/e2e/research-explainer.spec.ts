import { expect, test } from "@playwright/test";
import { verifyRunReplayIsolation } from "./runReplayIsolation";
import { isolationHeader } from "./strategyEnsembleIsolation";

test("Stored SMA explanation: explicit read, original references, pinned export and navigation", async ({ page, request, baseURL }) => {
  const token = process.env.E2E_STRATEGY_ENSEMBLE_TOKEN;
  await verifyRunReplayIsolation(baseURL, token, (url, options) => request.get(url, options));
  const headers = { [isolationHeader]: token! };
  await page.setExtraHTTPHeaders(headers);
  const seeded = await request.post(`${baseURL}/api/run-replay/demo`, { headers });
  expect(seeded.status()).toBe(200);
  const demo = await seeded.json();
  const mutations: string[] = [], explanations: string[] = [];
  page.on("request", (event) => {
    if (event.method() !== "GET") mutations.push(event.url());
    if (new URL(event.url()).pathname.startsWith("/api/research-explainer/")) explanations.push(event.url());
  });
  await page.goto("/");
  const sidebar = page.getByRole("navigation", { name: "Workspaces" });
  await sidebar.getByRole("button", { name: "Saved Backtests", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "Local SMA replay demo" });
  await row.getByRole("button", { name: "View", exact: true }).click();
  expect(explanations).toEqual([]);
  const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/research-explainer/saved-backtests/${demo.saved_backtest_id}`);
  await page.getByRole("button", { name: "Explain stored result", exact: true }).click();
  const response = await responsePromise; expect(response.status()).toBe(200);
  const pinned = await response.json();
  const panel = page.getByRole("region", { name: "Stored research explanation" });
  await expect(panel).toContainText("does not verify optional lifecycle or dataset links");
  await panel.getByRole("button", { name: "Inspect source total_return", exact: true }).click();
  await expect(page.getByRole("region", { name: "Evidence reference" })).toContainText("saved/metrics/total_return");
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  const waiting = page.waitForEvent("download");
  await panel.getByRole("button", { name: "Download explanation JSON" }).click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe(`quantlab-explanation-${demo.saved_backtest_id}.json`);
  const chunks: Buffer[] = [];
  for await (const chunk of (await download.createReadStream())!) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString("utf8"))).toEqual(pinned);
  await sidebar.getByRole("button", { name: "Home", exact: true }).click();
  expect(explanations).toHaveLength(1); expect(mutations).toEqual([]);
});
