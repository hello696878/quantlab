# QuantLab — Public Project Summary (Phase 38.0)

Three self-contained summaries for different readers. Copy-friendly; no fake
metrics, no live-data or production-trading claims.

---

## For recruiters (non-quant readers)

QuantLab is a solo-built, full-stack web platform for learning and
demonstrating quantitative finance. It has ~40 interactive workspaces — from
option pricing and yield curves to crypto risk and market microstructure —
each with editable inputs, charts, and the underlying formulas rendered next
to the numbers.

Engineering signals: a Python (FastAPI) backend with ~2,900 automated tests,
a TypeScript (Next.js) frontend with a shared design system, strict data
validation end to end, Docker Compose, GitHub Actions CI, and documentation
for every phase of the build. Product signals: guided demo tours, one-click
report exports, QA and data-reliability dashboards, and deliberate,
plain-language limitation statements in the UI.

Everything runs locally on deterministic sample data — no accounts, no API
keys, no live market feeds. It is an educational and portfolio project, not a
trading product.

## For quant researchers

QuantLab implements documented educational versions of standard models —
Black-Scholes/greeks/IV, CRR trees, Monte Carlo (Asian/barrier, Heston),
volatility surfaces and a variance-swap strip approximation, Vasicek/CIR,
Merton and reduced-form credit, cost-of-carry futures, MBS prepayment
(CPR/SMM/PSA), FX parity/carry, and microstructure analytics (microprice,
implementation shortfall, TCA attribution, VPIN-style toxicity) — plus a
crypto suite (perp funding/basis, DeFi health factors, tokenomics unlocks,
on-chain flows) and an alternative-data lab with explicit leakage guards.

Methodology is the point rather than performance: backtests are
lookahead-safe with explicit costs; the AFML lab covers triple-barrier
labeling, purged K-fold + embargo, sequential bootstrap, and fractional
differentiation; sample datasets are hand-written with designed failure modes
(one event set is constructed orthogonal to its signals so the IC read
honestly fails). A cross-lab scenario layer maps standardized shocks through
documented linear weight tables into module impact scores — a transparent
teaching approximation, never presented as calibrated risk. No result in the
platform is evidence of alpha, and the per-module simplifications are listed
in `docs/LIMITATIONS.md`.

## Technical architecture summary

- **Monorepo:** `backend/` (FastAPI, Python 3.11) + `frontend/` (Next.js 14
  app router, TypeScript, Tailwind) + `docs/` (per-phase roadmap,
  limitations ledger, demo scripts).
- **Backend pattern:** each lab is a package (`models.py` strict Pydantic v2
  schemas with `extra="forbid"` and finite-float types; `sample.py`
  deterministic hand-written samples; `service.py` pure analytics) exposed
  via `GET /<lab>/sample` + `POST /<lab>/analyze` routers registered in
  `app/main.py`. Validation errors return friendly 422s; no NaN/Infinity can
  enter or leave the API.
- **Frontend pattern:** per-lab typed API client in `src/lib/`, a panel
  component wired into a single-page shell (`AppShell` view union, grouped
  sidebar, command palette, dashboard cards). Debounced auto-analyze with
  AbortController; shared recharts components with non-finite filtering and
  empty states; local KaTeX formula panels with crash-proof fallbacks;
  app-router error/loading/not-found safety pages plus a root error boundary.
- **Persistence:** local SQLite for saved backtests/reports; optional
  browser-localStorage drafts (guarded, resettable). No cloud, no login, no
  telemetry.
- **Data policy:** deterministic static samples by default; optional external
  providers (yfinance, FRED, delayed quotes) are disabled by default, fail
  closed, and are never relied on in tests; the built-in pairs demo has a
  network-free fixture.
- **Quality:** ~2,900 deterministic backend tests (2,900 green as of Phase
  38.0), `tsc --noEmit` typechecking, GitHub Actions CI (backend tests +
  frontend build), Docker Compose, and in-app QA/reliability dashboards that
  document — but never replace — the local verification steps.
