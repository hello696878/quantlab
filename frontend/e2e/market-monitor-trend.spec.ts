/** Mocked production-UI verification only: no real backend or providers. */
import { expect, test } from "@playwright/test";
import { monitorCatalog, monitorHistory, monitorSnapshot } from "../src/test/fixtures/marketMonitor";
import { assertNoHorizontalOverflow } from "./helpers";

test.use({ timezoneId: "America/Los_Angeles" });

test("opens one trend independently and retains it on a failed refresh", async ({ page, baseURL }) => {
  const history: string[] = [];
  const unexpected: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  let releaseSnapshot!: () => void;
  const snapshotWait = new Promise<void>(resolve => { releaseSnapshot = resolve; });
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(baseURL!).origin) {
      unexpected.push(url.origin);
      return route.abort();
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data });
    switch (url.pathname) {
      case "/api/capabilities":
        return json({ schema: "serving_capabilities_v1", mode: "local", policy: "local_v1", corpus_id: null, synthetic: false, capabilities: ["local_research"] });
      case "/api/health": return json({ status: "ok" });
      case "/api/market-monitor/catalog": return json(monitorCatalog);
      case "/api/market-monitor/snapshot":
        await snapshotWait;
        return json(monitorSnapshot(url.searchParams.get("company") ?? "nvda"));
      case "/api/market-monitor/history": {
        const id = url.searchParams.get("instrument_id") ?? "";
        history.push(id);
        if (history.length === 3) {
          return json(monitorHistory(id, {
            status: "unavailable", points: [], retrieved_at: null, timezone: null,
            checked_at: "2026-11-10T10:16:00Z", message: "Trend provider unavailable in this fixture.",
          }));
        }
        return json(monitorHistory(id));
      }
      default:
        unexpected.push(url.pathname);
        return route.abort();
    }
  });
  try {
    await page.goto("/");
    const selectFirst = page.getByRole("button", { name: "View trend for S&P 500" });
    await expect(selectFirst).toBeVisible();
    expect(history).toEqual([]);
    await selectFirst.click();
    const first = page.getByRole("region", { name: "Trend for S&P 500" });
    const path = first.locator("path.recharts-line-curve");
    await expect(path).toBeVisible();
    expect(await path.getAttribute("d")).toMatch(/^M.*L/);
    await expect(page.getByText("Loading observations...")).toBeVisible();
    await first.getByText("Daily values (3)").click();
    await expect(first.getByRole("rowheader", { name: "2026-11-05" })).toBeVisible();
    await expect(first.getByRole("cell", { name: "100.125" })).toBeVisible();
    releaseSnapshot();
    await expect(page.getByRole("link", { name: /Fed statement/ })).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await first.screenshot({ path: test.info().outputPath("trend-desktop.png") });

    const selectSecond = page.getByRole("button", { name: "View trend for NVIDIA" });
    await selectSecond.click();
    const second = page.getByRole("region", { name: "Trend for NVIDIA" });
    await expect(second.locator("path.recharts-line-curve")).toBeVisible();
    await expect(first).toHaveCount(0);
    await second.getByText("Daily values (3)").click();
    await expect(second.getByRole("cell", { name: "123.5" })).toBeVisible();
    await second.getByRole("button", { name: "Refresh trend" }).click();
    await expect(second.getByText(/Showing the last successful trend/)).toBeVisible();
    await expect(second.getByText("Stale", { exact: true })).toBeVisible();
    await expect(second.getByRole("cell", { name: "123.5" })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await assertNoHorizontalOverflow(page);
    await expect(second.locator("path.recharts-line-curve")).toBeVisible();
    await second.screenshot({ path: test.info().outputPath("trend-mobile.png") });
    await second.getByRole("button", { name: "Close trend" }).press("Enter");
    await expect(second).toHaveCount(0);
    await expect(selectSecond).toBeFocused();
    expect(history).toEqual(["sp500", "nvda", "nvda"]);
    expect(unexpected).toEqual([]);
    expect(errors).toEqual([]);
  } finally {
    releaseSnapshot();
  }
});
