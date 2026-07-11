# QuantLab — Browser Smoke Test Report (Phase 42.1)

The first real end-to-end browser smoke test of the running application,
performed with in-browser tooling against the live dev servers. This is the
evidence record that backs the checklists in
[`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md) and
[`PUBLIC_RELEASE_CANDIDATE.md`](PUBLIC_RELEASE_CANDIDATE.md).

## Test context

| Field | Value |
|---|---|
| Test date | 2026-07-11 |
| Tested commit | `4e3606f` (Review ci preflight repo hygiene security sweep v1) **plus the uncommitted Phase 42.0 working tree** |
| Environment | Windows 11, embedded Chromium browser pane |
| Backend | uvicorn `app.main:app --reload`, http://localhost:8000 (`backend\venv`) |
| Frontend | `next dev --port 3000`, http://localhost:3000 |
| Integration path | Browser → same-origin `/api/*` → Next.js rewrite → `localhost:8000` (no CORS involved by design) |
| Viewports | 1440×900, 1024×800, 768×900 |
| Verification method | DOM probes (text, `scrollWidth` overflow, element rects, computed styles) + network request log + backend/frontend server logs + screenshots. Screenshots were captured in-session (the browser pane cannot export image files to the repo); repo-committed captures remain governed by [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md). |

## Routes tested (all 37 sidebar views)

Every sidebar entry was opened and audited for: correct title, substantial
rendered content, no `NaN`/`Infinity` in rendered output, no page-level
horizontal overflow, no error/unavailable state, no stuck loading state.

Start Here / Product Workflow: Home · Demo Center · Portfolio Showcase ·
Developer Onboarding · Global Markets Globe · Scenario Studio · Research
Workspace · Data Reliability Center · QA Command Center · Release Notes
Center · Public Release Candidate — **all PASS**.

Backtesting / Knowledge: Backtest · Strategy Comparison · Portfolio Backtest ·
CSV Backtest · Strategy Builder · Parameter Sweep · Train/Test Validation ·
Walk-Forward · Strategy Library · Paper Replications · Quant Disasters —
**all PASS**.

Labs: Portfolio Risk · Macro Regime · Crypto Derivatives · DeFi Risk ·
Tokenomics · On-Chain Analytics · Alternative Data · Market Microstructure ·
Event · Options · Volatility · Futures & Commodities · Real Estate · Credit
Risk · Yield Curve · FX · Cross-Sectional Scanner · AFML — **all PASS**.

Saved Work: Saved Backtests · Saved Reports · Settings — **all PASS**
(empty states render as controlled UI, backed by 200s from the SQLite-backed
endpoints).

The two "NaN/Infinity" text hits found were checklist *wording* on the QA
Command Center and Public Release Candidate pages ("no NaN/Infinity anywhere
visible") — documentation copy, not rendered values.

## Workflows tested

| # | Workflow | Result | Evidence |
|---|---|---|---|
| W1 | Landing dashboard: hero, stat strip, onboarding, nav cards | PASS | All `/api/health`, `/api/saved-backtests`, `/api/saved-reports` → 200; zero console errors |
| W2 | Frozen 7-stop public demo route + Onboarding + RC page | PASS | All titles/content verified; sample endpoints 200 |
| W3a | Scenario Studio template flip (Soft Landing → Severe Combo) | PASS | Severity 11.3 → 100.0; regime badge → "Severe systemic stress"; `POST /api/scenario-studio/analyze` → 200 |
| W3b | Crypto Derivatives shock slider (price +50%) | PASS | Debounced second `POST /api/crypto-derivatives/analyze` → 200; response verified: spot 65,000 → 97,500, position P&L and margin ratio recomputed, all values finite |
| W4 | Backtest engine — Pairs Trading KO/PEP (network-free demo pair) | PASS | `POST /api/backtest/pairs` → 200; 119 trades, paginated trade log, 4 charts, full performance summary (honest negative strategy result −23.0% vs +112.7% B&H); **no live provider touched** (KO/PEP is served by the deterministic fixture before any fetch; backend log shows zero errors/downloads) |
| W5 | Command palette (Ctrl+K) open, search, navigate, Escape | PASS | Entries found and navigable (incl. new Phase 42 entries) |
| W6 | SQLite-backed saved work reads | PASS | `GET /api/saved-backtests`, `/api/saved-reports` → 200; empty lists render as understandable empty states (no write was performed — the smoke test does not mutate user data) |
| W7 | Refresh + browser back/forward | PASS | Refresh restores Home (valid state); back/forward never broke the app. Note: in-app views don't sync to the URL (`?view=` is honored only for `globe`; unknown values fall back safely to Home) |
| W8 | Responsive 1440 / 1024 / 768 | PASS after fixes | Three defects found and fixed (below) |
| W9 | Network + server log audit | PASS | Every request same-origin `/api/*`; no unexpected 4xx/5xx; the only "failed" entries are `net::ERR_ABORTED` on mount-time sample fetches — the AbortController canceling the React StrictMode duplicate dev-mount request, each immediately followed by a 200 (expected dev behavior, not user-visible) |

## Defects found and fixed (all confirmed in-browser before fixing)

### D1 — MEDIUM (broken responsive layout): dashboard card badges overflow at 1024

- **Symptom:** page-level horizontal scrollbar on Home at 1024 px; feature-map
  card badges ("Futures analytics", "Real estate + MBS analytics",
  "Portfolio analytics + robustness", "Execution + liquidity analytics")
  escape their cards and overlap the neighboring column.
- **Repro:** viewport 1024×800 → Home → scroll to Feature Map.
  Measured: `scrollWidth − clientWidth = 33`; badge rects extended up to
  52 px past their card rects.
- **Root cause:** card title rows were non-wrapping
  (`flex items-center justify-between gap-2`) with `flex-shrink-0` badge
  pills; at 4-column widths a card (~200 px) is narrower than title + badge,
  and three pills are wider than the card itself.
- **Fix:** [`HomeDashboard.tsx`](../frontend/src/components/HomeDashboard.tsx) —
  title rows now `flex-wrap` (22 occurrences, uniform pattern) and badge
  pills `max-w-full truncate` instead of `flex-shrink-0` (21 occurrences).
- **After:** page overflow 0 at 1024/768; zero badge-vs-card overflows
  (36 badges measured); 1440 unchanged.

### D2 — MEDIUM (broken responsive layout): TopBar squeezes the title to ~140 px at 768

- **Symptom:** at 768 px the sticky header's title/subtitle column is ~140 px
  wide (sidebar 224 px + header controls ~330 px leave little room), so the
  long per-view subtitle renders as a ~30-line skinny column pushing content
  far down, with dead space beside it.
- **Repro:** viewport 768×900 → any view with a long subtitle (e.g. Scenario
  Studio).
- **Root cause:** non-wrapping header flex row; the controls keep intrinsic
  width and the title block absorbs all the squeeze.
- **Fix:** [`TopBar.tsx`](../frontend/src/components/TopBar.tsx) —
  `max-lg:flex-wrap` on the header (controls drop below the title only under
  1024 px) and `max-lg:line-clamp-2` on the subtitle. Desktop (≥1024)
  verified byte-identical in behavior: controls right-aligned on the same
  row, subtitle unclamped. (A first attempt with unconditional `flex-wrap`
  regressed 1440 — controls wrapped below the title — caught in-browser and
  corrected to the `max-lg:` variant.)
- **After:** header at 768 is 147 px tall, full-width title, 2-line subtitle,
  overflow 0.

### D3 — MINOR (visual): Global Markets chips clip their values at 768

- **Symptom:** the dashboard market chips show "+0." instead of "+0.32%" —
  the percentage span extended ~35 px past the 111 px chip card.
- **Repro:** viewport 768×900 → Home → Global Markets strip.
- **Root cause:** `sm:grid-cols-4` forces 4 columns while the sidebar leaves
  only ~488 px of content at 768 → 111 px chips can't fit label + value.
- **Fix:** [`HomeDashboard.tsx`](../frontend/src/components/HomeDashboard.tsx) —
  the markets grid is now `lg:grid-cols-4` (2 columns until 1024). The
  visually identical System Status grid was measured and does **not**
  overflow, so it was deliberately left unchanged.
- **After:** 233 px chips, values fully visible, zero overflow.

## Observations (recorded, deliberately not changed)

1. **In-app views are not URL-addressable** — refresh always restores Home;
   `?view=` works only for `globe`, and unknown values fall back safely to
   Home. Controlled behavior, matches the SPA design; deep links between
   product layers are already on the snapshot's improvement list.
2. **Clipboard writes are blocked in the embedded test browser**
   (`NotAllowedError`); copy buttons correctly showed the designed fallback
   ("Copy failed — select the text instead"). In a normal focused browser the
   copy succeeds — re-verify by hand during the user smoke pass.
3. **No frontend test framework exists** (documented limitation), so no
   automated regression test accompanies these CSS-only fixes; the regression
   guard is the responsive section of the smoke runbook plus this report's
   measurements.
4. The embedded pane occasionally screenshots stale/unpainted frames during
   dev-server hot reloads; every suspected visual defect in this report was
   therefore confirmed with DOM geometry probes before being recorded.

## Verification after fixes

- Full re-audit of key routes at 1440/1024/768: overflow 0 everywhere,
  header correct at all three widths, badges contained, chips readable.
- `npx tsc --noEmit` → exit 0.
- Backend: untouched by this phase (CSS-only frontend fixes); pairs/scenario/
  crypto endpoints exercised live and green. The full backend suite's known
  state as of Phase 42.0: 2,964 passed, 4 failed — all four caused by the
  untracked in-progress `backend/tests/fixtures/futures_csv/ym_roll.csv`
  (user work stream), unrelated to the frontend or this test.
- Both dev servers running clean: frontend compile OK, zero backend error
  lines for the entire session.

## Result

**Browser smoke test: PASS** (after the three responsive fixes), on the
primary workflow exercised end-to-end in a real browser: landing → demo
route → scenario analysis roundtrip → lab slider roundtrip → deterministic
pairs backtest with charts, tables, and honest metrics.

Not covered here and still user-run before the public freeze: `npm run build`
(production build), hand-verification of copy buttons in a normal browser,
screenshot captures per `SCREENSHOT_CHECKLIST.md`, and resolution of the
futures fixture test collision noted above.

---

## Phase 42.2 addendum — release gates resolved

The two open items above were closed in the release-gate pass (2026-07-11,
same environment):

- **Futures fixture collision resolved.** Root cause: the four folder-
  aggregate futures tests normalized the **live** fixtures folder (the
  scripts discover CSVs recursively), so their exact-count assertions
  depended on the developer's working tree — the legitimately added
  `ym_roll.csv` (YM roll-event fixture for the new YM continuous-build test)
  broke them. Fix: those tests now stage exactly `esm25.csv` + `nqm25.csv`
  into an isolated tmp dir and normalize that (assertions unchanged, nothing
  skipped or weakened; `ym_roll.csv` untouched and its YM coverage intact).
- **Authoritative backend run:**
  `backend\venv\Scripts\python.exe -m pytest backend\tests -q` from
  `C:\quantlab` → **2968 passed, 0 failed, 0 skipped in 241.55s, exit 0**;
  `artifacts\` absent before and after. (Count reconciliation: Phase 41's
  2,967 + 1 new YM test = 2,968.)
- **Production build:** `npm run build` → **exit 0, no warnings**; routes
  `/` (static), `/_not-found`, `/globe` (dynamic) generated; `.env.local`
  honored.
- **Production-mode smoke** (`next start --port 3100`, backend on 8000):
  landing, navigation, Scenario Studio roundtrip (11.3 → 100.0), pairs
  KO/PEP backtest (identical deterministic result: 119 trades, −23.0%),
  Saved Reports empty state — all green; every request 200 via the same
  `/api/*` rewrite (and no StrictMode abort artifacts in prod); the three
  responsive fixes re-verified at 1440/1024/768 in production. Dev
  configuration restored afterward.
- Release-evidence captures remain manual — see the Phase 42.2 section of
  [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md).
