# QuantLab — Demo Freeze Checklist (Phase 42.0)

A "demo freeze" pins the exact state of the repo before recording the demo
video, capturing final screenshots, and posting publicly — so what you show
is what the repo actually contains. Fill in the placeholders by hand; nothing
in this repo automates any of it.

## 1. Freeze record — COMPLETED (Phase 42.4)

| Field | Value |
|---|---|
| Freeze date | 2026-07-11 |
| Branch | `main` |
| Verified application commit | `c059c4e` (all release gates ran against this commit) |
| Freeze evidence commit | the commit targeted by the annotated release tag (contains this record + the R1–R5 evidence; recorded externally, not self-referentially) |
| Release tag | `v4.60.0-public-release-candidate-demo-freeze-v1` (created only after the evidence commit's own CI run is green) |
| Backend suite at freeze | **2,968 passed, 0 failed, exit 0** (241.55s; `artifacts\` absent before/after) |
| Frontend typecheck at freeze | `npx tsc --noEmit` → exit 0 |
| `npm run build` at freeze | exit 0, no warnings (routes `/`, `/_not-found`, `/globe ƒ`) |
| Production browser smoke | PASS (`next start --port 3100` against the real backend — see `BROWSER_SMOKE_TEST_REPORT.md`, Phase 42.2 addendum) |
| Application CI run | [29141440276](https://github.com/hello696878/quantlab/actions/runs/29141440276) on `c059c4e` — Backend Tests ✅, Frontend Build ✅ |
| Known limitations | [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) (public) · [`LIMITATIONS.md`](LIMITATIONS.md) (full ledger) |
| Approval state | ready for evidence-commit CI verification |

### R1–R5 release evidence (production build at `c059c4e`, SHA-256)

| # | Path | Dimensions | SHA-256 |
|---|---|---|---|
| R1 | `docs/screenshots/release_landing_1440.png` | 1440×900 | `46db0fd41c896987803520bcafb19585247df32658116aad95897b7c86d19334` |
| R2 | `docs/screenshots/release_scenario_studio.png` | 1243×781 | `2ebb4b28893257f9138290ac4855fc99e3b0a8c015d858efbbd25719231fc599` |
| R3 | `docs/screenshots/release_home_1024.png` | 1024×5800 | `98a3dde06e4a894176a3f942b75e9702f8c4cbfc450a43b51949c29ea13797bd` |
| R4 | `docs/screenshots/release_home_768.png` | 768×1000 | `d0b88dac5d968d7b1baf5ab1eaef376dc251d858b94242d5ea7d5b3fab6f71db` |
| R5 | `docs/screenshots/release_pairs_backtest.png` | 1042×1273 | `b271f413ce2426c81bca361a457df008103f5d366e65e4a319e32a68d5b32183` |

R1/R3/R4 were exported by OS-installed Edge headless (`--screenshot`) against
the production server; R2/R5 were captured manually from the same production
session. Capture recipes: `SCREENSHOT_CHECKLIST.md` §Release-evidence
captures.

## 2. Demo route order (frozen)

Present in exactly this order — it matches
[`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md):

1. Portfolio Showcase
2. Demo Center
3. Scenario Studio
4. Research Workspace
5. Data Reliability Center
6. QA Command Center
7. Release Notes Center

## 3. Screenshot list

- [ ] All captures in [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md)
      taken **at the frozen commit** (retake any that predate the freeze).
- [ ] Filenames include the page name; captions match what is on screen.
- [ ] No screenshot shows an error state, `NaN`, or dev-tools clutter.

## 4. Video demo list

- [ ] One rehearsal run of the chosen script length (90 s / 3 min / 7 min)
      completed without an unplanned page.
- [ ] Recording resolution and window size chosen (hide bookmarks/tabs).
- [ ] Script open on a second screen; timings from
      [`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) /
      [`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md).
- [ ] Recorded at the frozen commit; re-record if anything changes.

## 5. LinkedIn copy list

- [ ] Draft chosen from [`LINKEDIN_POST_DRAFTS.md`](LINKEDIN_POST_DRAFTS.md).
- [ ] Claims cross-checked against
      [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) — nothing
      the limitations doc contradicts.
- [ ] Repo link and (optional) video link verified after posting privately
      first.

## 6. README final check

- [ ] Renders cleanly on GitHub (headings, code blocks, tables).
- [ ] Every "Project docs" link resolves.
- [ ] Ground-rules blockquote intact; test counts match the latest real run.

## 7. Docs final check

- [ ] The six Phase 42 docs cross-link correctly.
- [ ] `docs/ROADMAP.md` has the current phase entry;
      `docs/LIMITATIONS.md` ledger is current.
- [ ] `VERSION`, `docs/VERSION_MANIFEST.md`, and the Release Notes Center
      page agree on the version label.

## 8. Known limitations final check

- [ ] [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) read once,
      top to bottom, against the actual product — nothing stale, nothing
      missing that a viewer would notice in the demo.

## 9. Do-not-change list (from freeze until the demo is published)

- **No new features.**
- **No styling rewrites** (theme tokens, layout, component styles).
- **No dependency upgrades** (`package.json`, `requirements.txt`).
- **No route renames** (View ids, sidebar labels, palette entries).
- **No external provider changes** (flags, defaults, fallbacks).
- **No CI workflow changes** (`.github/workflows/ci.yml`).
- **No generated cache commits** (`.next\`, `artifacts\`, `__pycache__`,
  `node_modules` — see [`REPOSITORY_HYGIENE.md`](REPOSITORY_HYGIENE.md)).

## 10. Allowed last-minute fixes (and nothing else)

- Typo fix (docs or UI copy).
- Broken link fix.
- Safety wording fix (removing an overclaim always qualifies).
- Screenshot caption fix.
- Route label fix (label text only — never the route id).

Anything bigger breaks the freeze: make the change, then re-run the smoke
pass in [`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md) and
restart this checklist with a new freeze record.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; not investment
advice; not production trading, risk, or compliance infrastructure. A freeze
is a discipline for honest demos — not a release certification.
