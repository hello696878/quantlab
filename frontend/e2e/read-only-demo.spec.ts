import { expect, test } from "@playwright/test";

test("Prepared read-only demo: approved browse, pinned explanation, proxy refusals and local assets", async ({ page, request, baseURL }, testInfo) => {
  const corpus = process.env.E2E_READ_ONLY_DEMO_CORPUS_ID;
  const backend = process.env.E2E_READ_ONLY_DEMO_BACKEND_URL;
  const setting = process.env.E2E_READ_ONLY_DEMO_PROXY_ONLY;
  if (setting !== undefined && setting !== "1") throw new Error("Invalid proxy-only acceptance setting");
  const proxyOnly = setting === "1";
  if (!corpus || !/^[0-9a-f]{64}$/.test(corpus) || !baseURL || (proxyOnly ? !!backend : !backend)) {
    throw new Error("Configure the owned corpus and loopback origins, or explicitly select proxy-only with no backend URL");
  }
  if (proxyOnly) testInfo.annotations.push({ type: "acceptance-scope", description: "Private container: browser/proxy only. Direct backend and physical corpus proofs must be retained separately by the operator." });
  for (const origin of backend ? [backend, baseURL] : [baseURL]) {
    const url = new URL(origin);
    if (!["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1"].includes(url.hostname) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      throw new Error("This bounded scenario requires clean loopback origins");
    }
  }
  const origins = [...(backend ? [backend.replace(/\/$/, "")] : []), `${baseURL.replace(/\/$/, "")}/api`];
  const headers = { "X-QuantLab-Expected-Corpus": corpus };
  // Observe public material as well as readiness. Backend owned-storage tests
  // separately attest DB/manifest/sidecar bytes; this is not a filesystem audit.
  const observed = new Map<string, string[]>();
  async function publicMaterial(origin: string): Promise<string[]> {
    const values: string[] = [];
    for (const path of ["/saved-backtests", "/saved-backtests/1", "/research-explainer/saved-backtests/1"]) {
      const response = await request.get(origin + path, { headers });
      expect(response.status()).toBe(200);
      values.push(await response.text());
    }
    return values;
  }
  for (const origin of origins) {
    const capabilities = await request.get(`${origin}/capabilities`);
    expect(capabilities.status()).toBe(200);
    expect(await capabilities.json()).toEqual({ schema: "serving_capabilities_v1", mode: "read_only_demo", policy: "read_only_demo_v1", corpus_id: corpus, synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] });
    const ready = await request.get(`${origin}/ready`);
    expect(ready.status()).toBe(200);
    expect((await ready.json()).corpus_id).toBe(corpus);
    observed.set(origin, await publicMaterial(origin));
    const stale = corpus === "a".repeat(64) ? "b".repeat(64) : "a".repeat(64);
    expect((await request.get(`${origin}/saved-backtests/1`, { headers: { "X-QuantLab-Expected-Corpus": stale } })).status()).toBe(409);
    for (const [method, path] of [["POST", "/saved-backtests"], ["DELETE", "/saved-backtests/1"], ["POST", "/custom-strategies/import"], ["POST", "/backtest/sma-crossover"]]) {
      expect((await request.fetch(origin + path, { method, data: "not parsed" })).status()).toBe(403);
    }
    expect((await request.get(`${origin}/globe/markets`)).status()).toBe(403);
    expect(await publicMaterial(origin)).toEqual(observed.get(origin));
  }
  if (!proxyOnly) expect(observed.get(origins[0])).toEqual(observed.get(origins[1]));
  const external: string[] = [], mutations: string[] = [], unpinned: string[] = [], unexpected: string[] = [];
  const approved = new Set(["/api/capabilities", "/api/health", "/api/ready", "/api/saved-backtests", "/api/saved-backtests/1", "/api/research-explainer/saved-backtests/1"]);
  page.on("request", (event) => {
    const url = new URL(event.url());
    if (["http:", "https:"].includes(url.protocol) && url.origin !== new URL(baseURL).origin) external.push(url.origin);
    if (event.method() !== "GET") mutations.push(url.pathname);
    if (url.pathname.startsWith("/api/")) {
      if (!approved.has(url.pathname)) unexpected.push(url.pathname);
      if (["/api/saved-backtests", "/api/saved-backtests/1", "/api/research-explainer/saved-backtests/1"].includes(url.pathname) && event.headers()["x-quantlab-expected-corpus"] !== corpus) unpinned.push(url.pathname);
    }
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
  await page.getByRole("button", { name: "Inspect source total_return", exact: true }).click();
  await expect(page.getByRole("region", { name: "Evidence reference" })).toContainText("saved/metrics/total_return");
  const checkResponse = page.waitForResponse((r) => {
    const url = new URL(r.url());
    return url.pathname === "/api/research-explainer/saved-backtests/1" && url.searchParams.get("expected") === JSON.parse(pinned).fingerprint;
  });
  await page.getByRole("button", { name: "Check pinned source", exact: true }).click();
  const checked = await checkResponse;
  expect(checked.status()).toBe(200); expect(await checked.text()).toBe(pinned);
  await expect(page.getByRole("button", { name: "Check pinned source", exact: true })).toBeEnabled();
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
  await page.goto("/?view=saved#run-replay=unapproved");
  await expect(page.getByRole("region", { name: "Read-only synthetic demo" })).toHaveAttribute("data-corpus-id", corpus);
  await expect(page.getByRole("button", { name: "Backtest", exact: true })).toBeDisabled();
  await page.goBack();
  await expect(page.getByRole("region", { name: "Read-only synthetic demo" })).toHaveAttribute("data-corpus-id", corpus);
  await expect(page.getByRole("button", { name: "Backtest", exact: true })).toBeDisabled();
  expect(mutations).toEqual([]); expect(external).toEqual([]);
  expect(unpinned).toEqual([]); expect(unexpected).toEqual([]);
  for (const origin of origins) {
    expect(await publicMaterial(origin)).toEqual(observed.get(origin));
    const ready = await request.get(`${origin}/ready`);
    expect(ready.status()).toBe(200); expect((await ready.json()).corpus_id).toBe(corpus);
  }
});
