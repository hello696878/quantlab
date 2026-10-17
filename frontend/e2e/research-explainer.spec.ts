import { expect, test } from "@playwright/test";
import { verifyRunReplayIsolation } from "./runReplayIsolation";
import { isolationHeader } from "./strategyEnsembleIsolation";
import type { ResearchExplanation } from "../src/lib/researchExplainer";

test("Stored SMA explanation: explicit read, original references, pinned export and navigation", async ({ page, request, baseURL }) => {
  const token = process.env.E2E_STRATEGY_ENSEMBLE_TOKEN;
  await verifyRunReplayIsolation(baseURL, token, (url, options) => request.get(url, options));
  const headers = { [isolationHeader]: token! };
  await page.setExtraHTTPHeaders(headers);
  const seeded = await request.post(`${baseURL}/api/run-replay/demo`, { headers });
  expect(seeded.status()).toBe(200);
  const demo = await seeded.json();
  // Setup explicitly executes the local engine and saves a root context before
  // the explanation-only request assertions begin.
  const savedResponse = await request.get(`${baseURL}/api/saved-backtests/${demo.saved_backtest_id}`, { headers });
  expect(savedResponse.status()).toBe(200);
  const saved = await savedResponse.json();
  const mutations: string[] = [], explanations: string[] = [];
  page.on("request", (event) => {
    if (event.method() !== "GET") mutations.push(event.url());
    if (new URL(event.url()).pathname.startsWith("/api/research-explainer/")) explanations.push(event.url());
  });
  await page.goto("/");
  const sidebar = page.getByRole("navigation", { name: "Workspaces" });
  await sidebar.getByRole("button", { name: "Saved Backtests", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "Local SMA replay demo" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button", { name: "View", exact: true }).click();
  expect(explanations).toEqual([]);
  const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/research-explainer/saved-backtests/${demo.saved_backtest_id}`);
  await page.getByRole("button", { name: "Explain stored result", exact: true }).click();
  const response = await responsePromise; expect(response.status()).toBe(200);
  const pinnedText = await response.text();
  const pinned: ResearchExplanation = JSON.parse(pinnedText);
  expect(pinned.identity.saved_backtest_id).toBe(demo.saved_backtest_id);
  expect(pinned.identity.trust).toBe("recorded_hashes_match");
  const totalReturn = pinned.facts.find((fact) => fact.id === "total_return");
  expect(totalReturn).toMatchObject({ source: "saved", path: "/metrics/total_return", state: "available",
    value: saved.metrics.total_return, unit: "decimal_return", rule: "percent_2" });
  const panel = page.getByRole("region", { name: "Stored research explanation" });
  await expect(panel).toContainText("does not verify optional lifecycle or dataset links");
  const inspect = panel.getByRole("button", { name: "Inspect source total_return", exact: true });
  await inspect.focus();
  await inspect.press("Enter");
  const evidence = page.getByRole("region", { name: "Evidence reference" });
  await expect(evidence).toContainText("saved/metrics/total_return");
  await expect(evidence).toContainText(JSON.stringify(saved.metrics.total_return));
  await expect(evidence).toContainText(`${totalReturn!.display} / decimal_return / percent_2`);
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  const waiting = page.waitForEvent("download");
  await panel.getByRole("button", { name: "Download explanation JSON" }).click();
  const download = await waiting;
  expect(download.suggestedFilename()).toBe(`quantlab-explanation-${demo.saved_backtest_id}.json`);
  const chunks: Buffer[] = [];
  const stream = await download.createReadStream();
  if (!stream) throw new Error("Explanation download has no readable contents");
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  const downloadedText = Buffer.concat(chunks).toString("utf8");
  expect(downloadedText).toBe(pinnedText);
  expect(JSON.parse(downloadedText)).toEqual(pinned);
  expect(explanations).toHaveLength(1);
  const check = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/research-explainer/saved-backtests/${demo.saved_backtest_id}`);
  await panel.getByRole("button", { name: "Check pinned source", exact: true }).click();
  const checked = await check;
  expect(checked.status()).toBe(200);
  expect(new URL(checked.url()).searchParams.get("expected")).toBe(pinned.fingerprint);
  expect(await checked.json()).toEqual(pinned);
  await expect(evidence).toHaveCount(0);
  await panel.getByRole("button", { name: "Inspect source total_return", exact: true }).click();
  // A separate, deliberate fixture deletion uses the same guarded disposable
  // harness. The subsequent explanation check itself remains a GET.
  const deleted = await request.delete(`${baseURL}/api/saved-backtests/${demo.saved_backtest_id}`, { headers });
  expect(deleted.status()).toBe(200);
  const missing = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/research-explainer/saved-backtests/${demo.saved_backtest_id}`);
  await panel.getByRole("button", { name: "Check pinned source", exact: true }).click();
  expect((await missing).status()).toBe(404);
  await expect(panel.getByRole("alert")).toContainText("Stored source not found or unavailable");
  await expect(evidence).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Download explanation JSON" })).toHaveCount(0);
  await sidebar.getByRole("button", { name: "Home", exact: true }).click();
  expect(explanations).toHaveLength(3); expect(mutations).toEqual([]);
});
