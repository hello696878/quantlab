/**
 * Responsive regression guard — 1440 / 1024 / 768 (Phase 43.0).
 *
 * Encodes the three defects found and fixed in the Phase 42.1 browser smoke
 * test as permanent geometry checks (no pixel/visual snapshots in v1):
 *
 *  D1 — HomeDashboard card badges overflowed their cards at 1024
 *       (fix: wrapping title rows + max-w-full truncate pills).
 *  D2 — TopBar squeezed the title/subtitle to a ~140px sliver at 768
 *       (fix: max-lg:flex-wrap + max-lg:line-clamp-2).
 *  D3 — Global Markets chip values clipped at 768
 *       (fix: markets grid stays 2-col until lg).
 *
 * All checks use real DOM geometry, mirroring the probes that verified the
 * fixes in the frozen release evidence.
 */

import { expect, test, type Page } from "@playwright/test";
import {
  assertNoHorizontalOverflow,
  gotoView,
  waitForAppSettled,
} from "./helpers";

const VIEWPORTS = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "laptop-1024", width: 1024, height: 900 },
  { name: "tablet-768", width: 768, height: 1000 },
] as const;

/** D1 guard: every dashboard badge pill must sit inside its card. */
async function assertBadgesInsideCards(page: Page): Promise<void> {
  const overflows = await page.evaluate(() => {
    const out: string[] = [];
    document
      .querySelectorAll('button.card span[class*="rounded-full"]')
      .forEach((b) => {
        const card = b.closest("button");
        if (!card) return;
        const br = b.getBoundingClientRect();
        const cr = card.getBoundingClientRect();
        if (br.right > cr.right + 1) {
          out.push(
            `${(b.textContent ?? "").trim().slice(0, 30)} (+${Math.round(br.right - cr.right)}px)`,
          );
        }
      });
    return out;
  });
  expect(overflows, `badges escaping their cards: ${overflows.join(", ")}`).toEqual([]);
}

/** D2 guard: the TopBar title block must never be an unreadable sliver. */
async function assertTopBarReadable(page: Page): Promise<void> {
  const width = await page.evaluate(() => {
    const h1 = document.querySelector("header h1");
    const block = h1?.closest("div");
    return block ? Math.round(block.getBoundingClientRect().width) : 0;
  });
  expect(width, `TopBar title block only ${width}px wide`).toBeGreaterThan(250);
  await expect(page.locator("header h1")).toBeVisible();
}

/** D3 guard: Global Markets chip values must not clip out of their chips. */
async function assertMarketChipsReadable(page: Page): Promise<void> {
  const clipped = await page.evaluate(() => {
    const out: string[] = [];
    const label = Array.from(document.querySelectorAll("span, div")).find(
      (e) => e.textContent?.trim() === "Americas",
    );
    const grid = label?.parentElement?.parentElement;
    if (!grid) return ["Global Markets strip not found"];
    grid.querySelectorAll(":scope > *").forEach((chip: Element) => {
      const cr = chip.getBoundingClientRect();
      chip.querySelectorAll("*").forEach((child: Element) => {
        const r = child.getBoundingClientRect();
        if (r.right > cr.right + 1) {
          out.push((child.textContent ?? "").trim().slice(0, 15));
        }
      });
    });
    return out;
  });
  expect(clipped, `chip content clipping: ${clipped.join(", ")}`).toEqual([]);
  // Values themselves are visible (percent strings rendered).
  await expect(
    page.locator("main").getByText(/[+-]\d+\.\d+%/).first(),
  ).toBeVisible();
}

for (const vp of VIEWPORTS) {
  test(`HomeDashboard geometry is sound at ${vp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/");
    await waitForAppSettled(page);

    await assertNoHorizontalOverflow(page, 2);
    await assertTopBarReadable(page);
    await assertBadgesInsideCards(page);
    await assertMarketChipsReadable(page);
  });

  test(`Public Release Candidate + Scenario Studio fit at ${vp.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/");
    await waitForAppSettled(page);

    await gotoView(page, "Public Release Candidate", /Public Release Candidate/);
    await assertNoHorizontalOverflow(page, 2);

    await gotoView(page, "Scenario Studio", /Scenario Studio/);
    await page.waitForTimeout(1_500); // sample + debounced analyze + charts
    await assertNoHorizontalOverflow(page, 2);
  });
}
