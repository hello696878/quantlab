# QuantLab — Final Smoke Test Runbook (Phase 42.0)

The hands-on, page-by-page manual verification pass behind
[`PUBLIC_RELEASE_CANDIDATE.md`](PUBLIC_RELEASE_CANDIDATE.md). Everything here
is done **by the user, by hand, in a normal browser** — there is no browser
automation in this repo, and this runbook does not add any. Budget roughly
45–60 minutes for the full pass.

> Deterministic sample data throughout; nothing here fetches live data. If a
> page fails a check, fix or note it — never share publicly with a known red
> failure and never claim the pass happened if it didn't.

> **Automated companion (Phase 43.0):** the frozen demo path, the Scenario
> Studio severe combo, the KO/PEP pairs fixture, and the 1440/1024/768
> geometry checks now also have a local Playwright guard —
> [`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md). It complements this
> manual pass; it does not replace it (it covers ~7 of the 37 views).

## 1. Before starting

- Clean tree: `git status --short` (only expected work in progress).
- Note the commit you are smoking: `git log -1 --oneline`.
- Close other apps using ports 8000 / 3000.
- Optional sanity: `.\scripts\check_environment.ps1` (read-only doctor).

## 2. Start the backend

```powershell
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Wait for `Application startup complete.` Leave this terminal open.

## 3. Start the frontend (dev server, user-run)

```powershell
cd C:\quantlab\frontend
npm run dev
```

Open http://localhost:3000. (The production build check is separate — §9.)

## 4. Test the dashboard

- Home loads with the greeting, stat cards, and suggested starting paths.
- Click 2–3 dashboard cards — each navigates to the right page and back
  (sidebar → Home) without errors.
- Open the command palette (Ctrl+K), type "scenario", press Enter — it
  navigates. Press Escape — it closes.

## 5. Test the product workflow pages

Visit each, apply the per-page checklist in §7:

| Page | Also specifically check |
|---|---|
| Portfolio Showcase | Copy-pitch buttons show "copied ✓"; demo-path deep links navigate |
| Demo Center | Pick a walkthrough; module health badges render; script builder copies |
| Scenario Studio | Flip Soft Landing → Severe Combo; charts + heatmap update; report copies |
| Research Workspace | Load a preset; run comparison renders; Markdown/JSON export copies |
| Data Reliability Center | Data-mode registry renders; reliability score finite; provider caveats visible |
| QA Command Center | Smoke matrix renders; release decision shows; command checklist copies |
| Release Notes Center | Version label + tag conventions render; template skeleton copies |
| Developer Onboarding | Command blocks copy; troubleshooting entries expand |
| Public Release Candidate | RC status cards render; demo pitch copies; doc paths listed |

## 6. Test the core research labs

Same §7 checklist on each. Interact at least once per page (move a slider,
change a select, click an analyze/preset control) and confirm numbers update
and stay finite.

1. Portfolio Risk Lab
2. Backtest Studio
3. Strategy Comparison
4. Macro Regime Lab
5. Crypto Derivatives Lab
6. DeFi Risk Lab
7. Tokenomics Lab
8. On-Chain Analytics Lab
9. Alternative Data Lab
10. Options Lab
11. Volatility Surface Lab
12. Market Microstructure Lab
13. Futures & Commodities Lab
14. Real Estate Lab
15. Credit Risk Lab

## 7. Per-page checklist (apply to every page above)

- [ ] Route loads (no blank screen, no infinite spinner).
- [ ] No red Next.js error overlay.
- [ ] No raw stack trace rendered in the page body.
- [ ] No `NaN`, `Infinity`, or `-Infinity` anywhere visible.
- [ ] No broken chart (empty axes with data expected, overlapping labels,
      chart error text).
- [ ] No broken formula (raw LaTeX/`$$` markup or KaTeX error boxes).
- [ ] No unreadable text (dark-on-dark, low-contrast values on cards).
- [ ] No horizontal page scrollbar at a normal desktop width (~1280 px);
      wide tables/code scroll inside their own container instead.
- [ ] Copy buttons (where present) show a success state and actually fill
      the clipboard.
- [ ] Export/report buttons (where present) produce well-formed
      Markdown/JSON.
- [ ] No live-trading wording — nothing implies orders, execution, or a
      connected broker.
- [ ] No investment-advice wording — no buy/sell/overweight/"you should"
      language anywhere in generated reports.

## 8. Responsive smoke

Repeat a lighter pass (load + look, no full interaction) at three widths on
the primary demo route (Portfolio Showcase → Demo Center → Scenario Studio →
Research Workspace → Data Reliability Center → QA Command Center → Release
Notes Center):

- **Desktop** ~1280–1440 px — normal layout, no overflow.
- **Tablet** ~768 px — cards reflow, sidebar still usable.
- **Mobile** ~375 px — no horizontal scroll; charts and tables scroll within
  their own containers; controls still tappable.

Use the browser devtools device toolbar; this stays a manual check.

## 9. Final commands (after the route pass)

```powershell
# Backend tests — from the repo root; artifacts\ must be absent afterwards
cd C:\quantlab
if (Test-Path .\artifacts) { Remove-Item -Recurse -Force .\artifacts }
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck
cd C:\quantlab\frontend
npx tsc --noEmit

# Frontend production build — ALWAYS user-run, never automated in this repo
npm run build
```

Record the actual pytest count and exit codes. If any command fails, the
smoke pass fails — fix first, then re-run.

## 10. Evidence collection

Keep alongside the filled-in status table in
[`PUBLIC_RELEASE_CANDIDATE.md`](PUBLIC_RELEASE_CANDIDATE.md):

- **Screenshots** — per [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md);
  filenames noted in the table.
- **Terminal output** — the final pytest summary line, `tsc` exit, and the
  `npm run build` success line (copy the real lines; don't paraphrase).
- **Commit hash** — `git log -1 --format=%h` for the exact commit smoked.
- **Tag name** — the tag created after review (expected pattern
  `v4.xx.0-short-feature-name-v1`; created manually by the user).
- **Notes** — anything odd, even if it passed; oddities become
  [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) entries or fix-phase candidates.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; no telemetry; not
investment advice; not production trading, risk, or compliance
infrastructure. No browser automation — this pass is deliberately human.
