import { expect, test } from "@playwright/test";

test("Prepared read-only demo: approved browse, pinned explanation, proxy refusals and local assets", async ({ page, request, baseURL }) => {
  const corpus = process.env.E2E_READ_ONLY_DEMO_CORPUS_ID;
  const backend = process.env.E2E_READ_ONLY_DEMO_BACKEND_URL;
  if (!corpus || !/^[0-9a-f]{64}$/.test(corpus) || !backend || !baseURL) throw new Error("Configure the owned prepared demo, expected corpus ID and both loopback origins before execution");
  for (const origin of [backend, baseURL]) {
    const url = new URL(origin);
    if (!["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1"].includes(url.hostname) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      throw new Error("This bounded scenario requires clean loopback origins");
    }
  }
  for (const origin of [backend.replace(/\/$/, ""), `${baseURL.replace(/\/$/, "")}/api`]) {
    const capabilities = await request.get(`${origin}/capabilities`);
    expect(capabilities.status()).toBe(200);
    expect(await capabilities.json()).toMatchObject({ schema: "serving_capabilities_v1", mode: "read_only_demo", policy: "read_only_demo_v1", corpus_id: corpus, synthetic: true });
    const ready = await request.get(`${origin}/ready`);
    expect(ready.status()).toBe(200);
    expect((await ready.json()).corpus_id).toBe(corpus);
    expect((await request.get(`${origin}/saved-backtests`, { headers: { "X-QuantLab-Expected-Corpus": corpus } })).status()).toBe(200);
    const stale = corpus === "a".repeat(64) ? "b".repeat(64) : "a".repeat(64);
    expect((await request.get(`${origin}/saved-backtests/1`, { headers: { "X-QuantLab-Expected-Corpus": stale } })).status()).toBe(409);
    for (const [method, path] of [["POST", "/saved-backtests"], ["DELETE", "/saved-backtests/1"], ["POST", "/custom-strategies/import"], ["POST", "/backtest/sma-crossover"]]) {
      expect((await request.fetch(origin + path, { method, data: "not parsed" })).status()).toBe(403);
    }
    expect((await request.get(`${origin}/globe/markets`)).status()).toBe(403);
  }
  const external: string[] = [], mutations: string[] = [];
  page.on("request", (event) => {
    const url = new URL(event.url());
    if (["http:", "https:"].includes(url.protocol) && url.origin !== new URL(baseURL).origin) external.push(url.origin);
    if (event.method() !== "GET") mutations.push(url.pathname);
  });
  await page.goto("/?view=backtest");
  await expect(page.getByRole("region", { name: "Read-only synthetic demo" })).toHaveAttribute("data-corpus-id", corpus);
  await expect(page.getByRole("button", { name: "Backtest", exact: true })).toBeDisabled();
  const row = page.getByRole("row").filter({ hasText: "Synthetic SMA showcase" });
  await expect(row.getByRole("button", { name: "Delete", exact: true })).toBeDisabled();
  await row.getByRole("button", { name: "View", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save Report", exact: true })).toHaveCount(0);
  const responsePromise = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/research-explainer/saved-backtests/1");
  await page.getByRole("button", { name: "Explain stored result", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const pinned = await response.text();
  expect(JSON.parse(pinned).identity.trust).toBe("legacy_unverified");
  const waiting = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download explanation JSON", exact: true }).click();
  const download = await waiting;
  const stream = await download.createReadStream();
  if (!stream) throw new Error("Download contents unavailable");
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  expect(Buffer.concat(chunks).toString("utf8")).toBe(pinned);
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  expect(mutations).toEqual([]); expect(external).toEqual([]);
});
