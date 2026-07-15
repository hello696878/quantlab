/**
 * Experiment Registry E2E coverage (Phase 48.0).
 *
 * Exercises the Research Experiment Registry view end to end against the running
 * backend: navigation, deterministic demo seeding, table rendering, filtering,
 * detail (fingerprints + reproducibility), two-experiment comparison, responsive
 * geometry, and the page-safety invariants.
 *
 * Isolation policy (see docs/EXPERIMENT_REGISTRY_RUNBOOK.md): the only write this
 * spec performs is the idempotent "Load demo registry" action, which inserts
 * clearly-marked demo records (stable demo_key) and NEVER overwrites or deletes
 * a real user record. The spec performs no baseline/delete/invalidate mutation —
 * those state transitions are covered exhaustively by the backend tests, which
 * run against isolated temporary SQLite databases.
 */

import { expect, test } from "@playwright/test";
import {
  assertNoFailedLocalRequests,
  assertNoHorizontalOverflow,
  expectNoRawStackTrace,
  expectNoVisibleNaNOrInfinity,
  gotoView,
  trackFailedLocalRequests,
  waitForAppSettled,
  type RequestFailure,
} from "./helpers";

const HEADER = /Research Experiment Registry/;

async function seedDemo(page: import("@playwright/test").Page): Promise<void> {
  // Idempotent: adds the 6 demo records if absent, otherwise a no-op. When the
  // registry is empty there are two "Load demo registry" affordances (the header
  // action and the empty-state action) — either seeds; use the first.
  await page.getByRole("button", { name: "Load demo registry" }).first().click();
  // Wait for the demo rows to appear (the reproduction-run row is demo-only).
  await expect(
    page.getByRole("button", { name: /Severe Stress \(reproduction run\)/ }),
  ).toBeVisible({ timeout: 20_000 });
}

test.describe("experiment registry", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Experiment Registry", HEADER);
  });

  test("opens with the local-first header and disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    // Panel-specific disclaimer copy (distinct from the TopBar subtitle).
    await expect(
      page.getByText(/Fingerprints and the reproducibility check are integrity aids/i),
    ).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("loads deterministic demo records and renders the table", async ({ page }) => {
    await seedDemo(page);
    // Summary card total and the flagship demo rows.
    await expect(
      page.getByRole("button", { name: /Severe Cross-Asset Stress Combo/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /KO\/PEP Pairs — Frozen Deterministic Backtest/ }),
    ).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters by module", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Module").selectOption("macro_regime");
    await expect(page.getByRole("button", { name: /Risk-Off Classification/ })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /KO\/PEP Pairs — Frozen Deterministic Backtest/ }),
    ).toHaveCount(0);
  });

  test("opens a detail with fingerprints and a reproducibility assessment", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Severe Stress \(reproduction run\)/ }).click();
    await expect(page.getByRole("heading", { name: /Severe Stress \(reproduction run\)/ })).toBeVisible();
    await expect(page.getByText(/Reproducibility assessment/i)).toBeVisible();
    // The reproduction run matches its baseline -> reproducible.
    await expect(page.getByText(/all match the reference/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Configuration", { exact: true })).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("compares two experiments with neutral differences", async ({ page }) => {
    await seedDemo(page);
    // Select the two macro-regime rows via their comparison checkboxes.
    await page.getByRole("checkbox", { name: /Select Macro Regime — Risk-Off \(partial reproduction\)/ }).check();
    await page.getByRole("checkbox", { name: /Select Macro Regime — Risk-Off Classification/ }).check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByText("Compare experiments")).toBeVisible();
    await expect(page.getByText(/Configuration fingerprint: match/)).toBeVisible();
    await expect(page.getByText(/Result fingerprint: differs/)).toBeVisible();
    await expect(page.getByText(/reported neutrally/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("has no horizontal overflow at 1024 and 768", async ({ page }) => {
    await seedDemo(page);
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.waitForTimeout(300);
    await assertNoHorizontalOverflow(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  // §16.15 — the dark-theme filter-control fix: the selects and the search input
  // must be dark surfaces, never the browser-default white.
  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    const controls = [
      page.getByLabel("Module"),
      page.getByLabel("Type"),
      page.getByLabel("Status"),
      page.getByLabel("Reproducibility"),
      page.getByLabel("Search"),
    ];
    for (const control of controls) {
      const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
      // Browsers differ in how they serialize color-mix() results: older
      // engines resolve to rgb(a), newer ones keep oklch(L C H) — where the
      // leading L is already a 0..1 lightness. Same assertion either way:
      // the surface must be dark, never the browser-default white.
      const rgb = bg.match(/rgba?\(([^)]+)\)/);
      if (rgb) {
        const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
        // Relative luminance — a dark surface sits well below 0.5; pure white is 1.
        const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        expect(luminance, `control background ${bg} should be dark, not white`).toBeLessThan(0.5);
      } else {
        const oklch = bg.match(/oklch\(\s*([\d.]+)/);
        expect(oklch, `background '${bg}' should be rgb(a) or oklch()`).not.toBeNull();
        expect(
          Number.parseFloat(oklch![1]),
          `control background ${bg} should be dark, not white`,
        ).toBeLessThan(0.5);
      }
    }
  });

  // §16.16 — the table-density fix: a long experiment name must truncate inside
  // its own cell and never render over the adjacent Module column.
  test("table name column truncates and does not overlap the next column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await seedDemo(page);
    const firstRow = page.locator("tbody tr").first();
    const nameCell = firstRow.locator("td").nth(1);
    const moduleCell = firstRow.locator("td").nth(2);
    // The post-seed refetch briefly swaps the table for the loading skeleton,
    // and boundingBox() does not auto-wait — reading mid-swap yields nulls.
    // Retry the whole geometry read until the table has settled.
    await expect(async () => {
      const nameBox = await nameCell.boundingBox();
      const moduleBox = await moduleCell.boundingBox();
      const btnBox = await nameCell.getByRole("button").boundingBox();
      expect(nameBox).not.toBeNull();
      expect(moduleBox).not.toBeNull();
      expect(btnBox).not.toBeNull();
      // The rendered name stays within its own cell (truncation works).
      expect(btnBox!.x + btnBox!.width).toBeLessThanOrEqual(nameBox!.x + nameBox!.width + 2);
      // Cells tile left-to-right without overlapping the Module column.
      expect(nameBox!.x + nameBox!.width).toBeLessThanOrEqual(moduleBox!.x + 2);
    }).toPass({ timeout: 20_000 });
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });
});
