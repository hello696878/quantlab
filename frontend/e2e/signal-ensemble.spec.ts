/**
 * Signal Ensemble Lab E2E coverage (Phase 61.0).
 *
 * Isolation policy (docs/SIGNAL_ENSEMBLE_RUNBOOK.md): this spec must run
 * against services configured with an isolated test database. It writes
 * the idempotent demo seeds only (unique demo_key; cascading through the
 * Phase 54/52/55/59 demo loaders) plus one deliberately rejected baseline
 * attempt. It never clears a database and performs no external network
 * access. */

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

const HEADER = /Signal Ensemble, Redundancy & Combination Lab/;

const BANNED_WORDING =
  /optimal ensemble|best ensemble|recommended signal|selected signal|proven independence|guaranteed diversification|validated combination|profitable ensemble|superior signal mix|production ensemble|institutional-grade ensemble|certified signal combination|guaranteed performance/i;

const NEGATION =
  /\b(?:not|never|nothing|neither|nor|without|cannot|isn't|does not|doesn't|no)\b/i;

/**
 * The lab's own disclaimers legitimately contain banned phrases inside
 * NEGATED sentences. Only an AFFIRMATIVE occurrence is a defect, so
 * negated sentences are dropped before matching.
 */
function expectNoAffirmativeOverclaim(body: string): void {
  const affirmative = body
    .split(/(?<=[.;:!?])\s+|\n+/)
    .filter((sentence) => !NEGATION.test(sentence))
    .join("\n");
  expect(affirmative).not.toMatch(BANNED_WORDING);
}

const API = "/api/signal-ensembles";

async function seedDemo(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Load demo runs" }).first().click();
  await expect(
    page.getByRole("button", { name: /Identical pair/ }),
  ).toBeVisible({ timeout: 240_000 });
}

async function runIdByQuery(page: Page, query: string): Promise<number> {
  const listing = await (await page.request.get(
    `${API}/runs?query=${encodeURIComponent(query)}`)).json();
  expect(listing.items.length).toBeGreaterThan(0);
  return listing.items[0].id as number;
}

async function openDetail(page: Page, name: RegExp): Promise<void> {
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("ensemble-detail")).toBeVisible();
}

async function backToList(page: Page): Promise<void> {
  await page.getByRole("button", { name: "← Back to runs" }).click();
  await expect(page.getByTestId("ensemble-runs-table")).toBeVisible();
}

async function expectDarkBackground(
  control: ReturnType<Page["getByLabel"]>,
): Promise<void> {
  const bg = await control.evaluate((el) => getComputedStyle(el).backgroundColor);
  const rgb = bg.match(/rgba?\(([^)]+)\)/);
  if (rgb) {
    const [r, g, b] = rgb[1].split(",").map((v) => Number.parseFloat(v));
    expect((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255,
      `background ${bg} should be dark`).toBeLessThan(0.5);
    return;
  }
  const oklch = bg.match(/oklch\(\s*([\d.]+)/);
  expect(oklch, `background '${bg}' should be rgb(a) or oklch()`).not.toBeNull();
  expect(Number.parseFloat(oklch![1]), `background ${bg} should be dark`)
    .toBeLessThan(0.5);
}

test.describe("signal ensemble lab", () => {
  let failures: RequestFailure[];

  test.beforeEach(async ({ page }) => {
    // seeding cascades several upstream demo loaders on a cold database
    test.setTimeout(300_000);
    failures = trackFailedLocalRequests(page);
    await page.goto("/");
    await waitForAppSettled(page);
    await gotoView(page, "Signal Ensemble Lab", HEADER);
  });

  test("opens with the alignment and no-selection disclaimers", async ({ page }) => {
    await expect(page.locator("header h1")).toHaveText(HEADER);
    await expect(page.getByText("Local-first").first()).toBeVisible();
    await expect(page.getByText(/never by row number/i).first()).toBeVisible();
    await expect(page.getByText(/selects a signal/i).first()).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    await expectNoRawStackTrace(page);
    assertNoFailedLocalRequests(failures);
  });

  test("demo loads idempotently and the runs table renders", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("ensemble-runs-table")).toBeVisible();
    await expect(page.getByRole("button", { name: /Baseline candidate/ })).toBeVisible();
    await page.getByRole("button", { name: "Load demo runs" }).first().click();
    await expect(page.getByText(/nothing duplicated/i)).toBeVisible({ timeout: 60_000 });
    await expect(
      page.getByRole("button", { name: /Identical pair/ }),
    ).toHaveCount(1);
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("summary cards and filters narrow the list", async ({ page }) => {
    await seedDemo(page);
    await expect(page.getByTestId("ensemble-summary-cards")).toBeVisible();
    await page.getByLabel("Mode", { exact: true }).selectOption("user_weights");
    await expect(page.getByRole("button", { name: /User-supplied static weights/ })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Identical pair/ }),
    ).toHaveCount(0);
    await page.getByLabel("Alignment", { exact: true }).selectOption("pairwise_complete");
    await expect(
      page.getByRole("button", { name: /User-supplied static weights/ }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(
      page.getByRole("button", { name: /Identical pair/ }),
    ).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("identical pair reads exactly 1 with correct overlap", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Identical pair");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    expect(Math.abs(pairwise.items[0].pearson - 1)).toBeLessThan(1e-12);
    expect(Math.abs(pairwise.items[0].spearman - 1)).toBeLessThan(1e-12);
    expect(pairwise.items[0].overlap_count).toBe(30);
    await openDetail(page, /Identical pair/);
    await expect(page.getByTestId("ensemble-pairwise")).toContainText("1.0000");
    await expect(page.getByTestId("ensemble-pairwise")).toContainText("30");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("inverse pair reads -1 with no recommended inversion", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Inverse pair");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    expect(Math.abs(pairwise.items[0].pearson + 1)).toBeLessThan(1e-12);
    await openDetail(page, /Inverse pair/);
    await expect(page.getByTestId("ensemble-pairwise")).toContainText("-1.0000");
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/recommended inversion|should be inverted/i);
    assertNoFailedLocalRequests(failures);
  });

  test("constant signal stays unavailable with a reason", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Constant signal");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    expect(pairwise.items[0].state).toBe("unavailable");
    expect(pairwise.items[0].pearson).toBeNull();
    await openDetail(page, /Constant signal/);
    await expect(page.getByTestId("ensemble-pairwise")).toContainText("unavailable");
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("heavy-tie pair shows tie counts and ranking policy", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Heavy-tie pair");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    const spearman = pairwise.items[0].correlations.spearman;
    expect(spearman.signal_tie_count).toBeGreaterThan(0);
    expect(pairwise.items[0].zero_sign_count).toBeGreaterThan(0);
    await openDetail(page, /Heavy-tie pair/);
    await expect(page.getByTestId("ensemble-missingness")).toContainText("average");
    assertNoFailedLocalRequests(failures);
  });

  test("pairwise-complete and strict intersection both stored with counts", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Pairwise-complete");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    const strict = pairwise.items.filter(
      (p: { alignment_mode: string }) => p.alignment_mode === "strict_intersection");
    const complete = pairwise.items.filter(
      (p: { alignment_mode: string }) => p.alignment_mode === "pairwise_complete");
    expect(strict.length).toBe(3);
    expect(complete.length).toBe(3);
    const abStrict = strict.find((p: { signal_a: string; signal_b: string }) =>
      p.signal_a === "sig-a" && p.signal_b === "sig-b");
    const abComplete = complete.find((p: { signal_a: string; signal_b: string }) =>
      p.signal_a === "sig-a" && p.signal_b === "sig-b");
    expect(abStrict.overlap_count).toBe(18);
    expect(abComplete.overlap_count).toBe(30);
    await openDetail(page, /Pairwise-complete versus strict/);
    await expect(page.getByTestId("ensemble-pairwise"))
      .toContainText(/pair-specific overlaps/);
    assertNoFailedLocalRequests(failures);
  });

  test("redundancy metrics and descriptive effective signal count", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Highly redundant trio");
    const matrix = await (await page.request.get(
      `${API}/runs/${id}/matrix`)).json();
    expect(Math.abs(matrix.diagnostics.effective_signal_count - 1))
      .toBeLessThan(1e-6);
    expect(Math.abs(matrix.redundancy.mean_absolute_correlation - 1))
      .toBeLessThan(1e-9);
    await openDetail(page, /Highly redundant trio/);
    await expect(page.getByTestId("ensemble-diagnostics"))
      .toContainText(/not the true number of independent signals/);
    await expect(page.getByTestId("ensemble-clustering")).toContainText("1 cluster");
    await backToList(page);
    await openDetail(page, /Lower-redundancy trio/);
    await expect(page.getByTestId("ensemble-diagnostics")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("rank-deficient matrix warns without silent repair", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Rank-deficient");
    const matrix = await (await page.request.get(
      `${API}/runs/${id}/matrix`)).json();
    expect(matrix.diagnostics.matrix_rank).toBe(2);
    expect(matrix.diagnostics.condition_number).toBeNull();
    await openDetail(page, /Rank-deficient similarity matrix/);
    await expect(page.getByTestId("ensemble-warnings")).toContainText(/rank deficient/);
    await expect(page.getByTestId("ensemble-diagnostics"))
      .toContainText(/unavailable/);
    assertNoFailedLocalRequests(failures);
  });

  test("equal-weight combination reconciles component contributions", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Equal-weight combination");
    const components = await (await page.request.get(
      `${API}/runs/${id}/components`)).json();
    expect(components.reconciliation.state).toBe("reconciled");
    const byKey = new Map<string, number>();
    for (const c of components.components) {
      if (c.missing) continue;
      const key = `${c.entity_id}|${c.timestamp}`;
      byKey.set(key, (byKey.get(key) ?? 0) + c.contribution);
    }
    for (const o of components.observations) {
      if (o.state !== "available") continue;
      const total = byKey.get(`${o.entity_id}|${o.timestamp}`);
      if (total !== undefined) {
        expect(Math.abs(total - o.combined_score)).toBeLessThan(1e-9);
      }
    }
    await openDetail(page, /Equal-weight combination/);
    await expect(page.getByTestId("ensemble-components")).toContainText("reconciled");
    await expect(page.getByTestId("ensemble-horizons")).toBeVisible();
    assertNoFailedLocalRequests(failures);
  });

  test("user weights show configured and effective values", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "User-supplied static weights");
    const components = await (await page.request.get(
      `${API}/runs/${id}/components`)).json();
    const weighted = components.components.find(
      (c: { configured_weight: number | null }) => c.configured_weight === 0.7);
    expect(weighted).toBeTruthy();
    await openDetail(page, /User-supplied static weights/);
    await expect(page.getByTestId("ensemble-components")).toContainText("0.7000");
    await expect(page.getByTestId("ensemble-components")).toContainText("0.3000");
    assertNoFailedLocalRequests(failures);
  });

  test("require-all leaves gaps unavailable with missing ids", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Require-all missing policy");
    const components = await (await page.request.get(
      `${API}/runs/${id}/components`)).json();
    const gaps = components.observations.filter(
      (o: { state: string }) => o.state === "unavailable");
    expect(gaps.length).toBe(4);
    expect(gaps[0].missing_signal_ids).toEqual(["sig-gap"]);
    await openDetail(page, /Require-all missing policy/);
    await expect(page.getByTestId("ensemble-components"))
      .toContainText(/never\s+zero-imputed/);
    assertNoFailedLocalRequests(failures);
  });

  test("renormalise-available shows effective weights and missing ids", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Renormalise-available");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.combination_coverage).toBe(1);
    const components = await (await page.request.get(
      `${API}/runs/${id}/components`)).json();
    const partial = components.observations.filter(
      (o: { component_count: number; state: string }) =>
        o.component_count === 2 && o.state === "available");
    expect(partial.length).toBe(4);
    await openDetail(page, /Renormalise-available missing policy/);
    await expect(page.getByTestId("ensemble-detail")).toContainText(/explicit opt-in/i);
    assertNoFailedLocalRequests(failures);
  });

  test("leave-one-out is neutral with no removal recommendation", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Component-contribution reconciliation");
    const loo = await (await page.request.get(
      `${API}/runs/${id}/leave-one-out`)).json();
    expect(loo.items.length).toBe(3);
    await openDetail(page, /Component-contribution reconciliation/);
    await expect(page.getByTestId("ensemble-loo")).toBeVisible();
    await expect(page.getByTestId("ensemble-loo"))
      .toContainText(/never an exclusion recommendation/);
    expectNoAffirmativeOverclaim(await page.locator("body").innerText());
    assertNoFailedLocalRequests(failures);
  });

  test("horizon comparison shows components and combination side by side", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Horizon-dependent response");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const combo = horizons.items.filter(
      (h: { scope: string }) => h.scope === "combination");
    const comps = horizons.items.filter(
      (h: { scope: string }) => h.scope === "component");
    expect(combo.length).toBe(2);
    expect(comps.length).toBe(2);
    const h1 = combo.find((h: { horizon: string }) => h.horizon === "1");
    const h4 = combo.find((h: { horizon: string }) => h.horizon === "4");
    expect(Math.abs(h1.spearman - h4.spearman)).toBeGreaterThan(0.05);
    await openDetail(page, /Horizon-dependent response/);
    await expect(page.getByTestId("ensemble-horizons")).toContainText("combination");
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/best horizon|optimal horizon/i);
    assertNoFailedLocalRequests(failures);
  });

  test("turnover comparison: cancelling and creating churn", async ({ page }) => {
    await seedDemo(page);
    const cancelId = await runIdByQuery(page, "Churning components");
    const cancel = await (await page.request.get(
      `${API}/runs/${cancelId}`)).json();
    expect(cancel.turnover_summary.mean_one_way_turnover).toBe(0);
    expect(Math.min(...(Object.values(cancel.component_turnover) as number[])))
      .toBeGreaterThan(0.4);
    const createId = await runIdByQuery(page, "Stable components");
    const create = await (await page.request.get(
      `${API}/runs/${createId}`)).json();
    expect(create.turnover_summary.mean_one_way_turnover).toBeGreaterThan(0.5);
    await openDetail(page, /Stable components, churning combination/);
    await expect(page.getByTestId("ensemble-turnover")).toBeVisible();
    await expect(page.getByTestId("ensemble-turnover"))
      .toContainText(/neither direction makes a combination better/);
    assertNoFailedLocalRequests(failures);
  });

  test("linked cost keeps gross and cost-adjusted separate", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Cost-linked combination");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const combo = horizons.items.find(
      (h: { scope: string; outcome_scope: string }) =>
        h.scope === "combination" && h.outcome_scope === "raw");
    expect(combo.top_minus_bottom).not.toBeNull();
    expect(combo.cost_adjusted_spread).not.toBeNull();
    expect(combo.cost_adjusted_spread).not.toBe(combo.top_minus_bottom);
    await openDetail(page, /Cost-linked combination/);
    await expect(page.getByTestId("ensemble-cost")).toBeVisible();
    await expect(page.getByTestId("ensemble-cost")).toContainText(/per-side/);
    await expect(page.getByTestId("ensemble-cost"))
      .toContainText(/Gross results never include costs/);
    assertNoFailedLocalRequests(failures);
  });

  test("training and held-out reported separately, nothing refitted", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Training versus held-out");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.held_out.training_observations).toBeGreaterThan(0);
    expect(run.held_out.held_out_observations).toBeGreaterThan(0);
    expect(run.integrity_status).toBe("verified_from_validation_split");
    await openDetail(page, /Training versus held-out/);
    await expect(page.getByTestId("ensemble-heldout")).toBeVisible();
    await expect(page.getByTestId("ensemble-heldout"))
      .toContainText(/nothing is refitted/);
    assertNoFailedLocalRequests(failures);
  });

  test("regime-shifting similarity uses stored assignments", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Regime-dependent similarity");
    const regimes = await (await page.request.get(
      `${API}/runs/${id}/regimes`)).json();
    expect(regimes.items.length).toBeGreaterThanOrEqual(2);
    await openDetail(page, /Regime-dependent similarity/);
    await expect(page.getByTestId("ensemble-regimes")).toBeVisible();
    await expect(page.getByTestId("ensemble-regimes"))
      .toContainText(/never recomputed/);
    assertNoFailedLocalRequests(failures);
  });

  test("factor comparison defers signal residualisation honestly", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "factor-residual");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.factor_residual.signal_value_residualisation.state)
      .toBe("deferred");
    const horizons = await (await page.request.get(
      `${API}/runs/${id}/horizons`)).json();
    const scopes = new Set(horizons.items
      .filter((h: { scope: string }) => h.scope === "combination")
      .map((h: { outcome_scope: string }) => h.outcome_scope));
    expect(scopes.has("raw")).toBe(true);
    expect(scopes.has("factor_residual")).toBe(true);
    await openDetail(page, /Raw versus factor-residual/);
    await expect(page.getByTestId("ensemble-factor")).toBeVisible();
    await expect(page.getByTestId("ensemble-factor"))
      .toContainText(/deferred/);
    assertNoFailedLocalRequests(failures);
  });

  test("comparison stays neutral with comparability warnings", async ({ page }) => {
    await seedDemo(page);
    const rows = page.getByTestId("ensemble-runs-table").locator("tbody tr");
    await rows.nth(0).getByRole("checkbox").check();
    await rows.nth(1).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Compare selected" }).click();
    await expect(page.getByTestId("ensemble-compare")).toBeVisible();
    await expect(page.getByText(/no winner\s+is declared/i)).toBeVisible();
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("baseline behaviour: eligible marked, descriptive rejected", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Baseline candidate");
    const run = await (await page.request.get(`${API}/runs/${id}`)).json();
    expect(run.is_baseline).toBe(true);
    expect(run.integrity_status).toBe("verified_point_in_time");
    await expect(page.getByText("★ baseline").first()).toBeVisible();
    // the assumed-availability descriptive run is refused (deliberate 409)
    await openDetail(page, /Independent-looking deterministic pair/);
    await page.getByRole("button", { name: "Mark as comparison baseline" }).click();
    await expect(page.getByText("Baseline rejected")).toBeVisible({ timeout: 20_000 });
    const unexpected = failures.filter((f) => !f.url.includes("mark-baseline"));
    assertNoFailedLocalRequests(unexpected);
  });

  test("export is schema-versioned and free of paths or credentials", async ({ page }) => {
    await seedDemo(page);
    const payload = await (await page.request.get(`${API}/export`)).json();
    expect(payload.schema_version).toBe("signal_ensemble_export_v1");
    expect(payload.disclaimer).toMatch(/proves signal/);
    const text = JSON.stringify(payload);
    for (const banned of ["C:\\\\", "/home/", "password", "api_key",
                          "secret", "quantlab.db"]) {
      expect(text).not.toContain(banned);
    }
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("Infinity");
    assertNoFailedLocalRequests(failures);
  });

  test("filter controls are dark and units are visible", async ({ page }) => {
    await seedDemo(page);
    await expectDarkBackground(page.getByLabel("Mode", { exact: true }));
    await expectDarkBackground(page.getByLabel("Integrity", { exact: true }));
    await expectDarkBackground(page.getByLabel("Alignment", { exact: true }));
    await expectDarkBackground(page.getByLabel("Search", { exact: true }));
    await openDetail(page, /Identical pair/);
    await expect(page.getByTestId("ensemble-missingness")).toContainText(/unit score/);
    await expect(page.getByTestId("ensemble-missingness")).toContainText("%");
    assertNoFailedLocalRequests(failures);
  });

  test("desktop, 1024 and 768 stay usable without overlap", async ({ page }) => {
    await seedDemo(page);
    await openDetail(page, /Equal-weight combination/);
    for (const width of [1440, 1024, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(150);
      await assertNoHorizontalOverflow(page);
      await expect(page.getByTestId("ensemble-pairwise")).toBeVisible();
    }
    await expectNoVisibleNaNOrInfinity(page);
    assertNoFailedLocalRequests(failures);
  });

  test("insufficient overlap discloses the pair-specific count", async ({ page }) => {
    await seedDemo(page);
    const id = await runIdByQuery(page, "Insufficient overlap");
    const pairwise = await (await page.request.get(
      `${API}/runs/${id}/pairwise`)).json();
    expect(pairwise.items[0].state).toBe("unavailable");
    expect(pairwise.items[0].reason).toContain("below the minimum");
    await openDetail(page, /Insufficient overlap/);
    await expect(page.getByTestId("ensemble-pairwise")).toContainText("unavailable");
    assertNoFailedLocalRequests(failures);
  });

  test("no NaN, no stack trace and no affirmative overclaim anywhere", async ({ page }) => {
    await seedDemo(page);
    expectNoAffirmativeOverclaim(await page.locator("body").innerText());
    for (const name of [/Identical pair/,
                        /Highly redundant trio/,
                        /Equal-weight combination/,
                        /Cost-linked combination/,
                        /Training versus held-out/,
                        /Baseline candidate/]) {
      await openDetail(page, name);
      await expectNoVisibleNaNOrInfinity(page);
      await expectNoRawStackTrace(page);
      expectNoAffirmativeOverclaim(await page.locator("body").innerText());
      await backToList(page);
    }
    assertNoFailedLocalRequests(failures);
  });
});
