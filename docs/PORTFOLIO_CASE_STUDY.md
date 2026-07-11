# QuantLab — Local-First Quant Research Platform (Portfolio Case Study)

A copy-ready case study for a personal site or profile README (Phase 44.0).
Every number below is a recorded, user-run result documented in this repo —
nothing is projected or invented.

## Problem

Quant research tooling tends to fail in three repeatable ways: it depends on
live data that breaks demos and tests; its assumptions live in someone's
head instead of on the page; and the gap between "works in my notebook" and
"can be demonstrated to another human" never closes. Most portfolio projects
in this space also overclaim — which is its own failure mode.

## Solution

QuantLab is a local-first **educational** research platform built to be
deterministic, explicit, and demonstrable: ~40 interactive research
workspaces that run entirely on documented sample data, with the formulas
rendered beside the numbers, a frozen browser-tested demo path, and
reproducible verification at every layer. It deliberately is **not** a
trading system — the honesty is architectural, enforced by tests.

## Architecture

- **Backend** — FastAPI + Pydantic v2; one package per lab (strict models
  with `extra="forbid"` and finite-float types, hand-written deterministic
  samples, pure service functions) behind a uniform
  `GET /<lab>/sample` + `POST /<lab>/analyze` contract.
- **Frontend** — Next.js 14 + TypeScript single-page shell: grouped sidebar,
  command palette, shared theme-aware charts, local KaTeX formula rendering
  (no CDNs).
- **Persistence** — local SQLite for saved work; no accounts, no cloud.
- **Data** — deterministic fixtures first; the few optional external
  adapters (yfinance history, opt-in FRED, delayed globe quotes) are
  disabled by default and fail closed to static data.
- **Quality** — ~2,900 deterministic backend tests, CI preflight (tests +
  typecheck + build), and a Playwright browser E2E guard that drives the
  OS-installed browser (zero downloads).

## Key modules

Backtest Studio (six strategies, cost models, robustness/stability labs) ·
Portfolio Risk Lab · Scenario Studio (cross-lab stress with documented
impact weights) · Options/Volatility, Rates/FX, Credit, Futures &
Commodities, Real Estate/MBS labs · AFML methodology lab · crypto
derivatives/DeFi/tokenomics/on-chain labs · Global Markets Globe · Release
Notes Center · the in-app Public Release Candidate page.

## Engineering highlights

- **No-lookahead discipline** — signals shift before P&L everywhere;
  lookahead safety is pinned by tests.
- **Deterministic fixtures** — the KO/PEP pairs demo reproduces 119 trades
  exactly, on any machine, with no network.
- **Wording contracts as tests** — generated reports cannot say "buy,"
  "recommend," or claim verification that didn't run; the test suite
  enforces the product's honesty.
- **Browser-level verification** — a manual 37-view smoke test found three
  real responsive defects (fixed the same day); a 12-test Playwright guard
  now encodes them as permanent geometry checks.
- **Release engineering** — a frozen demo path with five production-build
  screenshots (SHA-256 recorded), an evidence commit, an annotated tag, and
  observed-CI citations — never "trust me."
- **Repo hygiene** — zero-secrets-by-design, documented ignore policy,
  read-only helper scripts, CI that is described as a preflight signal, not
  a certification.

## Demo evidence (all user-run, recorded in the repo)

- All 37 sidebar views browser smoke-tested (dev **and** production mode).
- Scenario Studio severe stress combo: severity 11.3 → **100.0/100**, 8/8
  modules, analyze POST 200.
- KO/PEP pairs fixture: **119 trades, −23.0%** vs **+112.7%** buy-and-hold —
  a deliberately honest losing-strategy demo.
- Playwright E2E: **12/12 passed** against both dev and production builds.
- Backend suite: **2,968 passed, exit 0**; typecheck and production build
  clean; CI runs cited by ID in the freeze record.
- Five frozen screenshots: `docs/screenshots/release_*.png`.

## Limitations (deliberate)

Educational only; not production trading and not investment advice; no
broker/exchange connectivity; deterministic/static data where documented;
local-first single-user (no auth or hosting); E2E/CI green is a regression
signal, not certification. Full public ledger:
[`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md).

## What I learned

Productizing research is mostly *constraint* engineering: making
determinism, honesty, and reproducibility structural instead of aspirational.
Testable financial software needs the wording tested, not just the math.
Demos are a design target — a frozen, evidence-backed demo path changed how
I built everything upstream of it. And browser-level regression testing
catches an entire class of defects (hydration races, geometry overflow)
that unit tests can't see.

## Future roadmap

E2E in CI once the harness has a longer stability record · the recorded demo
video · richer docs navigation · optional live-data adapters with
fail-closed provenance labeling · deeper factor/risk model validation labs.

---

*Not investment advice; not a trading system; educational sample data
throughout.*
