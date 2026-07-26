/**
 * Dataset Lineage E2E coverage (Phase 49.0).
 *
 * Exercises the Data Provenance & Dataset Lineage view end to end: navigation,
 * idempotent demo lineage seeding, table + filters, dataset detail with version
 * history, the SVG lineage graph (and its tabular fallback), version comparison
 * with neutral schema drift, quality warnings, experiment links, export safety,
 * dark-theme filter controls, column-overlap geometry, responsive behavior, and
 * the page-safety invariants.
 *
 * Isolation policy (docs/DATASET_LINEAGE_RUNBOOK.md): the only writes this spec
 * performs are the idempotent demo-seed actions, which insert clearly-marked
 * demo records (unique demo_key) and never overwrite or delete real data.
 * Destructive transitions (invalidate) are covered by backend tests on isolated
 * temporary databases. No external network, no live providers.
 */

import { expect, test, type Page } from "@playwright/test";
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

const HEADER = /Data Provenance & Dataset Lineage/;

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo lineage" }).first().click();
  await expect(
    page.getByRole("button", { name: /Demo — Alt Sentiment Sample/ }),
  ).toBeVisible({ timeout: 20_000 });
}

/** Background must be dark in either rgb() or oklch() serialization. */
async function expectDarkBackground(control: ReturnType<Page["getByLabel"]>): Promise<void> {
  const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
  const rgb = bg.match(/rgba?\(([^)]+)\)/);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    expect(luminance, `control background ${bg} should be dark, not white`).toBeLessThan(0.5);
    return;
  }
  const oklch = bg.match(/oklch\(\s*([\d.]+)/);
  expect(oklch, `background '${bg}' should be rgb() or oklch()`).not.toBeNull();
  expect(Number.parseFloat(oklch![1]), `control background ${bg} should be dark`).toBeLessThan(0.5);
}

test.describe("dataset lineage", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Dataset Lineage", HEADER);
  });

  test("opens with the local-first header and provenance disclaimer", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(
      page.getByText(/not a regulatory audit trail, not tamper-proof/i).first(),
    ).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo lineage loads idempotently and the table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByRole("button", { name: /Raw KO\/PEP Price Fixture/ })).toBeVisible();
    // Re-seed: nothing duplicated (still exactly one Alt Sentiment row).
    await page.getByRole("button", { name: "Load demo lineage" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /Demo — Alt Sentiment Sample/ })).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filters narrow the table", async ({ page }) => {
    await seedDemo(page);
    await page.getByLabel("Domain").selectOption("macro");
    await expect(page.getByRole("button", { name: /Raw Macro Fixture/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Raw KO\/PEP Price Fixture/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByRole("button", { name: /Raw KO\/PEP Price Fixture/ })).toBeVisible();
  });

  test("dataset detail shows versions, fingerprints, lineage graph, and links", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Severe Cross-Asset Scenario Inputs/ }).click();
    await expect(page.getByRole("heading", { name: /Severe Cross-Asset Scenario Inputs/ })).toBeVisible();
    await expect(page.getByText(/Version history \(1\)/i)).toBeVisible();
    await expect(page.getByText("Manifest fingerprint")).toBeVisible();
    // SVG lineage graph with its accessible label; ancestors reachable.
    const svg = page.locator("svg[role=img]");
    await expect(svg).toBeVisible();
    await expect(svg).toHaveAttribute("aria-label", /Lineage graph/);
    await expect(page.getByText(/Parents \(this version was derived from\)/i)).toBeVisible();
    await expect(page.getByText(/Normalized Macro Factors/).first()).toBeVisible();
    // Linked experiment from the demo chain.
    await expect(page.getByText(/Severe Cross-Asset Stress Combo/).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("quality warning and invalidated version render on the alt-data example", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Alt Sentiment Sample/ }).click();
    await expect(page.getByText(/Version history \(2\)/i)).toBeVisible();
    // v1 row: open it and confirm the invalidation banner + warning checks.
    await page.getByRole("button", { name: "v1", exact: true }).click();
    await expect(page.getByText(/Invalidated .* superseded by v2/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("missing_ratio_within_limit")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("version comparison reports neutral schema drift", async ({ page }) => {
    await seedDemo(page);
    await page.getByRole("button", { name: /Demo — Alt Sentiment Sample/ }).click();
    await expect(page.getByText(/Version history \(2\)/i)).toBeVisible();
    await page.getByRole("checkbox", { name: "Select version v1 for comparison" }).check();
    await page.getByRole("checkbox", { name: "Select version v2 for comparison" }).check();
    await page.getByRole("button", { name: /Compare selected versions \(2\/2\)/ }).click();
    await expect(page.getByText("Compare dataset versions")).toBeVisible();
    await expect(page.getByText(/column added/i).first()).toBeVisible();
    await expect(page.getByText(/column removed/i).first()).toBeVisible();
    await expect(page.getByText(/reported neutrally/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls use dark theme backgrounds (never white)", async ({ page }) => {
    const controls = [
      page.getByLabel("Source"),
      page.getByLabel("Domain"),
      page.getByLabel("Format"),
      page.getByLabel("Quality"),
      page.getByLabel("Provenance"),
      page.getByLabel("Search"),
    ];
    for (const control of controls) {
      await expectDarkBackground(control);
    }
  });

  test("table name column does not overlap the adjacent column", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await seedDemo(page);
    const firstRow = page.locator("tbody tr").first();
    const nameCell = firstRow.locator("td").nth(0);
    const sourceCell = firstRow.locator("td").nth(1);
    // The post-seed refetch briefly swaps the table for the loading skeleton,
    // and boundingBox() does not auto-wait — reading mid-swap yields nulls.
    // Retry the whole geometry read until the table has settled.
    await expect(async () => {
      const nameBox = await nameCell.boundingBox();
      const sourceBox = await sourceCell.boundingBox();
      const btnBox = await nameCell.getByRole("button").boundingBox();
      expect(nameBox).not.toBeNull();
      expect(sourceBox).not.toBeNull();
      expect(btnBox).not.toBeNull();
      // The rendered name stays within its own cell (truncation works).
      expect(btnBox!.x + btnBox!.width).toBeLessThanOrEqual(nameBox!.x + nameBox!.width + 2);
      // Cells tile left-to-right without overlapping the Source column.
      expect(nameBox!.x + nameBox!.width).toBeLessThanOrEqual(sourceBox!.x + 2);
    }).toPass({ timeout: 20_000 });
    await assertNoHorizontalOverflow(page);
    assertNoFailedLocalRequests(failures);
  });

  test("no horizontal page overflow at 1024 and 768", async ({ page }) => {
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
});
