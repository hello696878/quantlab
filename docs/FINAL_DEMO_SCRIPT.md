# QuantLab — Final Demo Script (Phase 42.0)

The frozen presentation script for the public release candidate — three
timed lengths over the same route order, with per-page talking points,
clicks, and capture notes. Rehearse at the frozen commit
([`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md)); recording setup
lives in [`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md).

> Everything shown runs on deterministic educational sample data. Say so —
> it is a strength of the demo, not a caveat to hide.

## Route order (all three lengths use this spine)

1. Portfolio Showcase → 2. Demo Center → 3. Scenario Studio →
4. Research Workspace → 5. Data Reliability Center →
6. QA Command Center → 7. Release Notes Center

The 90-second cut uses stops 1–3 + the closing line; the 3-minute cut uses
1–5; the 7-minute cut uses all seven with the extra beats marked **[7-min]**.

## 1 · Portfolio Showcase — ~15 s / 25 s / 60 s

- **Say:** "QuantLab is a local-first, deterministic, educational quant
  research platform — about forty interactive labs behind one shell. This
  page is the summary: what it demonstrates, and just as deliberately, what
  it doesn't do — no live trading, no advice, everything on documented
  sample data."
- **Click:** scroll the highlights once; **[7-min]** click one copy-pitch
  button to show the copy UX.
- **Capture:** hero + ground-rules badge.

## 2 · Demo Center — ~20 s / 35 s / 75 s

- **Say:** "The product ships its own guided demos. Each module carries an
  honest health record — status, data mode, whether it has a backend
  endpoint — hand-maintained and kept truthful by tests."
- **Click:** open one walkthrough; **[7-min]** show the module health grid
  and one data-mode badge up close.
- **Capture:** module health dashboard.

## 3 · Scenario Studio — ~25 s / 45 s / 90 s

- **Say:** "Cross-lab scenario analysis: pick a template and documented
  weight tables map the shocks into impact scores across the labs — every
  formula is on the page, nothing is a black box."
- **Click:** flip Soft Landing → Severe Combo; point at the heatmap
  changing; **[7-min]** open the Markdown report and copy it.
- **Capture:** heatmap mid-comparison; the report panel.
- 90-second cut: jump to the closing line after this page.

## 4 · Research Workspace — ~30 s / 70 s

- **Say:** "Research needs memory: saved presets, an experiment journal, and
  a reproducibility score — the workflow layer most demo projects skip."
- **Click:** load a preset, show the run comparison; **[7-min]** export
  Markdown and show the disclaimer footer it always carries.
- **Capture:** comparison view.

## 5 · Data Reliability Center — ~30 s / 60 s

- **Say:** "Every module declares its data mode. The few optional external
  providers are off by default and fail closed to static data — and the test
  suite never depends on any of them."
- **Click:** scan the registry; **[7-min]** show a provider caveat entry.
- **Capture:** data-mode registry.
- 3-minute cut: closing line after this page.

## 6 · QA Command Center — ~45 s **[7-min]**

- **Say:** "Release readiness as a product surface: a smoke matrix, a scored
  readiness read, and the exact verification commands. It shows the
  commands — it never claims they ran. That honesty rule is itself a test."
- **Click:** smoke matrix; copy one command from the checklist.
- **Capture:** release decision card.

## 7 · Release Notes Center — ~30 s **[7-min]**

- **Say:** "And the release story: version manifest, changelog by area, and
  a release-notes template that separates tests actually run from tests
  expected. Roughly three thousand deterministic backend tests back all of
  this — the real count per phase is recorded in the roadmap."
- **Click:** version card; the template skeleton.
- **Capture:** version card.

## What NOT to say (any length, any audience)

- No production-trading claim — it does not trade, by design.
- No investment advice — never describe an output as a recommendation.
- No "guaranteed alpha," no performance promises of any kind.
- No live-data guarantee — optional providers are opt-in and fail closed.
- No compliance certification — QA layers are product workflow, not
  regulation.
- No invented metrics — no users, customers, or revenue; cite only the test
  count from a run you actually did.

## Closing lines

- **GitHub (README/We):** "A deterministic, local-first educational quant
  research platform — ~40 labs, a tested product workflow layer, and honest
  docs. Not a trading system; that's the point."
- **LinkedIn:** "I built QuantLab to practice building a research platform
  end to end — FastAPI + Next.js, thousands of deterministic tests, and
  wording rules enforced by the test suite. Educational only, and honest
  about it. Repo + limitations doc in the comments."
- **Interview:** "The interesting engineering isn't the formulas — it's
  keeping forty labs deterministic, tested, and honestly labeled. Happy to
  go as deep as you like on any layer."

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; not investment
advice; not production trading, risk, or compliance infrastructure.
