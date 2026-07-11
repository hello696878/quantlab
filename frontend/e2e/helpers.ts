/**
 * Shared helpers for the QuantLab frozen-demo E2E harness (Phase 43.0).
 *
 * Selector policy: prefer visible, frozen-page text and accessible roles over
 * CSS internals. Assertions test user-visible outcomes, not implementation
 * details. Nothing here mutates persistent user data (each test runs in a
 * fresh browser context) and nothing calls external networks.
 */

import { expect, type Page } from "@playwright/test";

/** Give the SPA time to mount and fire its debounced sample/analyze calls. */
export async function waitForAppSettled(page: Page): Promise<void> {
  await expect(page.locator("header h1")).toBeVisible({ timeout: 30_000 });
  // Sample-on-mount + ~300ms debounced analyze; generous but bounded.
  await page.waitForTimeout(1_200);
}

/**
 * Navigate the single-page shell by clicking a sidebar entry.
 * QuantLab views are not URL-addressable (by design), so navigation is the
 * same sidebar click a user performs.
 */
export async function gotoView(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: label, exact: true }).first().click();
  await page.waitForTimeout(900); // view mount + debounced analyze kickoff
}

/** Open the command palette with the real keyboard shortcut. */
export async function openCommandPalette(page: Page): Promise<void> {
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Command palette" }),
  ).toBeVisible({ timeout: 5_000 });
}

/** Dismiss the palette / any escapable overlay if one is open. */
export async function maybeDismissOverlays(page: Page): Promise<void> {
  const dialog = page.getByRole("dialog");
  if (await dialog.count()) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  }
}

/**
 * No rendered NaN / Infinity anywhere on the page.
 *
 * Documented exception: the QA Command Center and Public Release Candidate
 * pages legitimately contain checklist WORDING like "No NaN / Infinity
 * anywhere visible" — that documentation phrasing is stripped before the
 * check so only real rendered values can fail it.
 */
export async function expectNoVisibleNaNOrInfinity(page: Page): Promise<void> {
  const text = await page.locator("body").innerText();
  const scrubbed = text
    .replace(/no nan\s*\/\s*infinity[^\n]*/gi, "")
    .replace(/nan\s*\/\s*infinity/gi, "");
  expect(scrubbed, "rendered NaN/Infinity found on page").not.toMatch(
    /\bNaN\b|\bInfinity\b|\b-Infinity\b/,
  );
}

/** No raw JS/Python stack trace rendered in the page body. */
export async function expectNoRawStackTrace(page: Page): Promise<void> {
  const text = await page.locator("body").innerText();
  expect(text, "raw stack trace rendered on page").not.toMatch(
    /^\s+at .+:\d+:\d+\)?$/m,
  );
  expect(text).not.toMatch(/Traceback \(most recent call last\)/);
}

/** If the TopBar API health chip is rendered, it must report ONLINE. */
export async function expectApiOnlineIfShown(page: Page): Promise<void> {
  const chip = page.locator("header", { hasText: "API" });
  if (await chip.count()) {
    await expect(chip.getByText("ONLINE", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
  }
}

/** Page-level horizontal overflow check via real DOM geometry. */
export async function assertNoHorizontalOverflow(
  page: Page,
  allowedTolerancePx = 2,
): Promise<void> {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(
    overflow,
    `horizontal document overflow of ${overflow}px`,
  ).toBeLessThanOrEqual(allowedTolerancePx);
}

export interface RequestFailure {
  url: string;
  detail: string;
}

/**
 * Track failing LOCAL application requests for the lifetime of a page.
 *
 * Rules (documented in docs/BROWSER_E2E_RUNBOOK.md):
 *  - Any /api/* response with status >= 400 is a failure — the frozen demo
 *    path has no expected 4xx/5xx.
 *  - `net::ERR_ABORTED` is ignored: in dev, React StrictMode double-mounts
 *    effects and the AbortController cancels the duplicate sample fetch;
 *    each abort is immediately followed by a 200 (verified in the Phase 42.1
 *    smoke evidence). Favicon noise is ignored as harmless.
 */
export function trackFailedLocalRequests(page: Page): RequestFailure[] {
  const failures: RequestFailure[] = [];
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/") && res.status() >= 400) {
      failures.push({ url, detail: `HTTP ${res.status()}` });
    }
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    const err = req.failure()?.errorText ?? "unknown";
    if (err.includes("ERR_ABORTED")) return; // StrictMode duplicate-mount abort
    if (url.includes("favicon")) return;
    if (!url.includes("localhost")) return; // only local app traffic matters
    failures.push({ url, detail: err });
  });
  return failures;
}

export function assertNoFailedLocalRequests(failures: RequestFailure[]): void {
  expect(
    failures,
    `failed local requests: ${failures.map((f) => `${f.detail} ${f.url}`).join(", ")}`,
  ).toEqual([]);
}

/** Console error collector (best-effort diagnostic; asserted where stable). */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
}
