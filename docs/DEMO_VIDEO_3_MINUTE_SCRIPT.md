# 3-Minute Demo Video Script (Phase 44.0)

Timestamped, word-for-word, with fallbacks. Setup/retakes:
[`DEMO_VIDEO_SHOT_LIST.md`](DEMO_VIDEO_SHOT_LIST.md).

## 0:00–0:20 — Intro *(on: Home, fresh load)*

**Say:** "This is QuantLab, a local-first educational quant research
platform. About forty interactive workspaces — backtesting, portfolio risk,
scenario stress, options, credit, crypto, market microstructure — behind
one shell, and every workspace runs on deterministic sample data with the
formulas rendered next to the numbers."

**Click:** slow scroll: hero → Global Markets ("Static sample" badge in
frame) → Quick Actions.

## 0:20–0:50 — Architecture *(on: Home; sidebar hover while talking)*

**Say:** "The backend is FastAPI with strict Pydantic models — NaN and
Infinity can't cross the API boundary. The frontend is Next.js and
TypeScript with shared theme-aware charts and local formula rendering — no
CDNs. Saves go to local SQLite; there are no accounts and no cloud. The few
optional data adapters are disabled by default and fail closed to static
data, and the test suite never touches a live provider. Roughly
twenty-nine-hundred deterministic backend tests — including tests on the
*wording*, so a generated report can't drift into advice."

**Click:** hover sidebar groups; open Options Lab briefly as a lab example;
return Home.

## 0:50–1:20 — Product map *(navigate while talking)*

**Say:** "Beyond the labs there's a product layer: guided demos, a research
workspace with an experiment journal, a data-reliability registry, a QA
command center — and this Public Release Candidate page, where release
readiness is tracked honestly: every status is a recorded user-run check."

**Click:** sidebar → Demo Center (beat) → Public Release Candidate; hover
the RC status cards and the version/tag cards.

**Fallback:** if a page loads slowly, stay on it and keep narrating — never
mid-shot switch; retake the segment if it stalls past ~three seconds.

## 1:20–1:50 — Scenario Studio *(on: Scenario Studio)*

**Say:** "Scenario Studio runs one stress template through documented
weight tables into every module. Watch the severe cross-asset combo:
composite severity goes to one hundred out of one hundred, eight of eight
modules, and the heatmap shows exactly which shock groups drive which
modules. Nothing is a black box — the weights and formulas are on the
page."

**Click:** sidebar → Scenario Studio → click **Severe Cross-Asset Stress
Combo** → let the gauge land on 100.0 → scroll to the heatmap.

**Fallback:** if analyze lags, hover the template descriptions while it
completes; the gauge landing is the beat that matters.

## 1:50–2:20 — KO/PEP pairs fixture *(on: Backtest)*

**Say:** "The backtest demo is a deterministic fixture — the KO/PEP pairs
strategy reproduces exactly one hundred nineteen trades on any machine,
with no network. Minus twenty-three percent against a buy-and-hold of plus
one-twelve — the demo strategy loses, deliberately. This platform's job is
honest workflows, not signals."

**Click:** sidebar → Backtest → **Pairs Trading** card → Run Backtest →
scroll: performance summary → equity curve → trade log.

**Fallback:** the run takes five to fifteen seconds — rehearse once so the
wait lands inside the narration; if it exceeds the beat, cut the wait in
edit, never speed up the claim.

## 2:20–2:40 — Release evidence *(on: docs/screenshots or GitHub view)*

**Say:** "The public release is frozen and evidence-backed: five
production-build screenshots with hashes recorded in the freeze record, a
browser smoke test across all thirty-seven views, and an annotated release
tag. Every claim in this video is a recorded result in the repo docs."

**Click:** show `docs/screenshots/` (the five `release_*.png`) and the
freeze record table in `DEMO_FREEZE_CHECKLIST.md`.

## 2:40–3:00 — E2E guard + close *(terminal/report, then Home)*

**Say:** "And the demo path you just watched is protected by a twelve-test
Playwright regression guard — the route walk, the scenario result, the
pairs fixture, and responsive geometry at three widths. Educational by
design: not a trading system, not advice — and the docs say exactly what it
isn't. Repo link below."

**Click:** show a `12 passed` run you actually performed today → cut to
Home → hold two beats → end.

## Exact page order (for the editor)

Home → (Options Lab beat) → Demo Center → Public Release Candidate →
Scenario Studio → Backtest/Pairs → docs/screenshots + freeze record →
E2E output → Home.

## What NOT to claim (any take)

Production readiness / certification / audit · investment, trading, or
allocation advice · alpha or performance ("the demo loses" is the only
performance line) · live-data guarantees · users, customers, revenue ·
"CI/E2E guarantees correctness" — they're regression signals on specific
commits.

## Ground rules

Deterministic educational sample data; not investment advice; not
production trading, risk, or compliance infrastructure.
