# Demo Video Shot List (Phase 44.0)

Shot-by-shot capture plan for the QuantLab demo video, built on the frozen
v4.60/v4.61 demo path. Scripts: [`DEMO_VIDEO_90_SECOND_SCRIPT.md`](DEMO_VIDEO_90_SECOND_SCRIPT.md) ·
[`DEMO_VIDEO_3_MINUTE_SCRIPT.md`](DEMO_VIDEO_3_MINUTE_SCRIPT.md). The frozen
screenshots (`docs/screenshots/release_*.png`) are the visual reference for
what each shot should look like — never regenerate or overwrite them.

## 1. Recording setup

- Browser window ~1440×900 (matches the frozen evidence), dark theme,
  bookmarks bar and extensions hidden; record the page area only.
- Backend on **:8000** (`venv\Scripts\uvicorn app.main:app --reload --port 8000`).
- Frontend: production preferred — `npm run build` then
  `npx next start --port 3100`. **Never run `next dev` and `next start`
  simultaneously** (they share `.next`; the dev server corrupts the
  production assets — see `BROWSER_E2E_RUNBOOK.md`).
- Clean demo state: fresh page load, command palette closed, no leftover
  test tabs; terminal windows off-screen (no paths/usernames on camera).
- No desktop/private info anywhere in frame; do a private full-run screen
  check before recording for real.

## 2. Shot order

| # | Shot | Page / route | Click | Expected visible result | Narration point | Reference | Avoid saying |
|---|---|---|---|---|---|---|---|
| 1 | Landing | Home (fresh load) | none — let it breathe | Hero, API **ONLINE**, Global Markets strip with "Static sample" badge | "Local-first educational quant research platform — ~40 deterministic workspaces" | `release_landing_1440.png` | "production-ready", any performance words |
| 2 | Portfolio Showcase | sidebar → Portfolio Showcase | scroll highlights once | Pitch cards, demo path, ground-rules badge | "The platform presents itself honestly — what it does and deliberately doesn't" | SCREENSHOT_CHECKLIST #optional | "users", "customers" |
| 3 | Public Release Candidate | sidebar → Public Release Candidate | hover RC status cards | Version/tag cards, statuses reading "Manual — not yet run" | "Release readiness as a product surface — nothing claims a pass it didn't earn" | in-app page | "certified" |
| 4 | Scenario Studio | sidebar → Scenario Studio | click **Severe Cross-Asset Stress Combo** | Severity **100.0/100**, 8/8 modules, red gauge, heatmap | "One template maps through documented weights into every module — all formulas on the page" | `release_scenario_studio.png` | "risk system", forecasts |
| 5 | KO/PEP Pairs | sidebar → Backtest → Pairs Trading → Run | wait for results | 119 trades, −23.0% vs +112.7%, equity curve | "Deterministic fixture — same 119 trades on every machine; the strategy loses, and honest numbers are the point" | `release_pairs_backtest.png` | anything implying a signal or advice |
| 6 | Saved Reports | sidebar → Saved Reports | none | Clean list or friendly empty state | "Local SQLite persistence — no accounts, no cloud" | — | — |
| 7 | Command Palette | Ctrl+K, type "scenario" | Enter | Palette opens, navigates | "Everything is reachable from the keyboard" | — | — |
| 8 | E2E result | terminal (pre-recorded/clean) OR HTML report | show `12 passed` line / report summary | Playwright list output, green | "A 12-test browser guard pins this exact demo path — run locally, evidence in the repo" | ROADMAP 43.0 entry | "certified", "CI guarantees" |
| 9 | Docs / release package | editor or GitHub view of `docs/` | scroll the release docs | RELEASE_ASSET_MANIFEST, freeze record | "Every claim in this video is a recorded, user-run result documented here" | `RELEASE_ASSET_MANIFEST.md` | — |

Shot 8 must show a run you actually performed; if you haven't re-run E2E on
recording day, run it first or cut the shot — never show stale output as if
fresh.

## 3. Retake checklist (inspect every take before keeping it)

- [ ] No `NaN` / `Infinity` anywhere on screen.
- [ ] No red error overlay, no raw stack trace.
- [ ] No broken/empty charts where data is expected.
- [ ] TopBar title/subtitle readable (not clipped or squeezed).
- [ ] No horizontal overflow / stray scrollbar at the recording width.
- [ ] No private info: usernames, file paths, other windows, notifications.
- [ ] Numbers on screen match the frozen evidence (severity 100.0; 119
      trades; −23.0% / +112.7%).

## Ground rules (unchanged by this doc)

The video shows an educational platform on deterministic sample data — no
investment advice, no live-trading claims, no performance promises.
