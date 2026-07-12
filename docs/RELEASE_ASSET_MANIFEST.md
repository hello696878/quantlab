# Release Asset Manifest (Phase 44.0)

The authoritative inventory of every public-release asset: what it is, where
it lives, whether it is frozen evidence or reproducible/copy material, and
how it relates to the release commits and tags.

Key commits/tags referenced below: application state `c059c4e` · freeze
evidence commit `7cf9708` (tag `v4.60.0-public-release-candidate-demo-freeze-v1`)
· E2E guard `e1dcdca` + stabilization `4a06c5b` (tag
`v4.61.0-browser-e2e-regression-guard-v1`).

| Asset | Path | Type | Purpose | Frozen / Generated / Copy | Commit/Tag relationship | Notes |
|---|---|---|---|---|---|---|
| Landing screenshot 1440 | `docs/screenshots/release_landing_1440.png` | PNG | R1 release evidence | **Frozen evidence** | committed in `7cf9708`; SHA-256 in freeze record | never overwrite/regenerate |
| Scenario Studio screenshot | `docs/screenshots/release_scenario_studio.png` | PNG | R2 release evidence | **Frozen evidence** | committed in `7cf9708` | never overwrite/regenerate |
| Home 1024 screenshot | `docs/screenshots/release_home_1024.png` | PNG | R3 release evidence (badge containment) | **Frozen evidence** | committed in `7cf9708` | never overwrite/regenerate |
| Home 768 screenshot | `docs/screenshots/release_home_768.png` | PNG | R4 release evidence (responsive header/chips) | **Frozen evidence** | committed in `7cf9708` | never overwrite/regenerate |
| Pairs backtest screenshot | `docs/screenshots/release_pairs_backtest.png` | PNG | R5 release evidence (119 trades) | **Frozen evidence** | committed in `7cf9708` | never overwrite/regenerate |
| Browser smoke report | `docs/BROWSER_SMOKE_TEST_REPORT.md` | doc | Manual 37-view smoke evidence + 42.2 addendum | Frozen record (42.3-era addenda only) | describes `c059c4e` | evidence record; successor pointer to E2E |
| Demo freeze checklist | `docs/DEMO_FREEZE_CHECKLIST.md` | doc | Freeze record: dates, hashes, evidence SHA-256 | **Frozen record** | §1 completed at `7cf9708` | do not edit the completed record |
| Final smoke runbook | `docs/FINAL_SMOKE_TEST_RUNBOOK.md` | doc | Manual page-by-page verification procedure | Living doc | — | complements the E2E guard |
| Final demo script | `docs/FINAL_DEMO_SCRIPT.md` | doc | Live-presentation scripts (90s/3m/7m) | Living doc | frozen route | superseded for video by the 44.0 scripts below |
| E2E runbook | `docs/BROWSER_E2E_RUNBOOK.md` | doc | How to run the Playwright guard | Living doc | v4.61 series | servers user-started |
| Frozen demo regression guard | `docs/FROZEN_DEMO_REGRESSION_GUARD.md` | doc | What is protected; change policy | Living doc | v4.60/v4.61 | update with any deliberate demo change |
| Playwright setup | `docs/PLAYWRIGHT_SETUP.md` | doc | One-time E2E setup | Living doc | v4.61 series | zero browser downloads by default |
| GitHub release draft | `docs/GITHUB_RELEASE_DRAFT_v4.61.md` | doc | **Manual copy-paste** release text | Copy material | targets tag `v4.61.0-…` | no automatic publishing, ever |
| LinkedIn launch post | `docs/LINKEDIN_LAUNCH_POST.md` | doc | Post drafts + reply templates | Copy material | v4.61 announcement | claims cross-checked vs limitations |
| Portfolio case study | `docs/PORTFOLIO_CASE_STUDY.md` | doc | Personal-site / profile write-up | Copy material | v4.60/v4.61 evidence | recorded numbers only |
| Demo video shot list | `docs/DEMO_VIDEO_SHOT_LIST.md` | doc | Recording plan + retake checklist | Copy material | frozen demo path | frozen screenshots are the visual reference |
| 90-second video script | `docs/DEMO_VIDEO_90_SECOND_SCRIPT.md` | doc | Timestamped short script | Copy material | frozen demo path | exact words + clicks |
| 3-minute video script | `docs/DEMO_VIDEO_3_MINUTE_SCRIPT.md` | doc | Timestamped long script | Copy material | frozen demo path | includes slow-page fallbacks |
| E2E run outputs | `artifacts/e2e/**` (test-results, playwright-report) | generated | Local E2E traces/reports | **Generated — never committed** | gitignored via `artifacts/` | safe to delete; regenerated per run |
| Manual CI browser E2E workflow | `.github/workflows/browser-e2e.yml` | workflow | Run the E2E guard in an isolated runner (`workflow_dispatch` only) | Source | v4.63 series (Phase 45.0) | read-only perms; no secrets; never publishes anything |
| CI browser E2E doc | `docs/CI_BROWSER_E2E.md` | doc | How to trigger/interpret the manual workflow | Living doc | v4.63 series | remote-run status recorded only from real observed runs |
| CI E2E evidence artifacts | GitHub Actions run artifacts (`browser-e2e-evidence-<run id>`) | generated | Per-run logs/report/traces, 14-day retention | **Generated — never committed** | attached to a specific workflow run | temporary CI evidence — not frozen screenshots, not certification |

## Policies (binding)

- **Frozen evidence stays frozen** — the five `release_*.png` files and the
  completed freeze record are historical facts of `7cf9708`; a future
  release mints a *new* evidence set instead of touching them.
- **Generated is never committed** — everything under `artifacts/e2e/` is
  disposable local output.
- **Publishing is always manual** — the GitHub release draft is pasted by a
  human into the GitHub UI; nothing in this repo calls the GitHub API or
  creates releases/tags automatically.
- Copy material must be re-checked against
  [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) before each
  public use.

## Ground rules (unchanged by this doc)

Educational platform on deterministic sample data — not investment advice,
not production trading, risk, or compliance infrastructure.
