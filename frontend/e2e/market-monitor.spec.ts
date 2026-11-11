/** Mocked UI acceptance only: no backend, providers, SQLite or external network. */
import { expect, test } from "@playwright/test";
import { monitorCatalog, monitorSnapshot } from "../src/test/fixtures/marketMonitor";
import { assertNoHorizontalOverflow } from "./helpers";

test("Monitor watchlist, company, refresh and existing research navigation with mocked API", async ({ page }) => {
  const apiCalls: string[] = [];
  const blocked: string[] = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) { blocked.push(url.hostname); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    apiCalls.push(url.pathname + url.search);
    let value: unknown;
    if (url.pathname === "/api/capabilities") value = { schema: "serving_capabilities_v1", mode: "local", policy: "local_v1", corpus_id: null, synthetic: false, capabilities: ["local_research"] };
    else if (url.pathname === "/api/health") value = { status: "ok" };
    else if (url.pathname === "/api/market-monitor/catalog") value = monitorCatalog;
    else if (url.pathname === "/api/market-monitor/snapshot") value = monitorSnapshot(url.searchParams.get("company") ?? "nvda");
    else { blocked.push(url.pathname); return route.abort(); }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(value) });
  });
  await page.goto("/");
  await expect(page.locator("header h1")).toHaveText("Market Monitor");
  await expect(page.getByRole("link", { name: /Fed statement/ })).toBeVisible();
  await page.getByRole("combobox", { name: "Add instrument" }).selectOption("aapl");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Move up Apple" }).click();
  await page.getByRole("combobox", { name: "Selected company" }).selectOption("aapl");
  await expect(page.getByRole("region", { name: "Selected company" })).toContainText("222.00");
  await page.getByRole("button", { name: "Remove S&P 500" }).click();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: test.info().outputPath("monitor-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: test.info().outputPath("monitor-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Backtest", exact: true }).click();
  await expect(page.locator("header h1")).toHaveText("Backtest");
  const before = apiCalls.filter((path) => path.startsWith("/api/market-monitor/snapshot")).length;
  await page.waitForTimeout(350);
  expect(apiCalls.filter((path) => path.startsWith("/api/market-monitor/snapshot")).length).toBe(before);
  await page.getByRole("button", { name: "Monitor", exact: true }).click();
  await expect(page.locator("header h1")).toHaveText("Market Monitor");
  expect(blocked).toEqual([]);
  expect(apiCalls[0]).toBe("/api/capabilities");
});
