# LinkedIn Launch Post — QuantLab v4.61 (Phase 44.0)

Three post lengths for the public-release announcement, plus captions,
hashtags, and reply templates. Honest and technical — no hype, no invented
metrics. Cross-check every claim against
[`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) before posting.

## 1. Short version (~60 words)

> I've released QuantLab — a local-first quant research platform I built to
> practice engineering financial software properly: ~40 deterministic
> educational research labs (FastAPI + Next.js + SQLite), a frozen,
> screenshot-evidenced demo path, and a Playwright browser regression guard
> protecting it. Educational only, honest about its limits — and that's the
> point. Repo + limitations doc in the comments.

## 2. Medium version (~120 words)

> QuantLab started as a backtesting engine and became a study in
> productizing quant research: a local-first platform with ~40 interactive
> workspaces — backtesting, portfolio risk, scenario stress, options, credit,
> crypto/DeFi, market microstructure — all on deterministic sample data with
> the formulas rendered next to the numbers.
>
> The part I'm proudest of isn't a model. It's the release engineering:
> a frozen public demo path with production screenshots and SHA-256'd
> evidence, ~2,900 deterministic backend tests (wording rules are tests
> too), and a Playwright browser E2E guard that fails loudly if the frozen
> demo ever regresses.
>
> Educational only — no live trading, no advice, and the docs say exactly
> what it isn't. Repo in the comments.

## 3. Technical version (~180 words)

> Shipped: QuantLab v4.61 — local-first quant research platform + browser
> E2E regression guard.
>
> Stack: FastAPI + Pydantic v2 (strict models, finite-float guards at the
> API boundary), Next.js 14 + TypeScript, SQLite for local persistence,
> Playwright for browser regression.
>
> Engineering decisions I'd defend in an interview:
> • Deterministic fixtures everywhere — the KO/PEP pairs demo reproduces 119
>   trades bit-for-bit; tests never depend on a live provider.
> • Honest-labeling as tests — report wording that would imply advice or
>   claim unrun verification fails the backend suite.
> • A frozen demo freeze: five production-build screenshots, hashes in the
>   freeze record, and a 12-test Playwright guard (zero browser downloads —
>   it drives OS-installed Edge) that pins the demo path, the scenario
>   engine's severe-stress output, and three previously-fixed responsive
>   defects.
> • Optional data adapters are off by default and fail closed to static
>   data.
>
> It's educational by design — not a trading system, not advice. The
> limitations doc ships with the repo, and it's the first thing I'd show
> you. Link in comments.

## 4. Screenshot caption ideas

- `release_landing_1440.png` — "One shell, ~40 deterministic research
  workspaces. API health, honest data-mode badges."
- `release_scenario_studio.png` — "One scenario template drives every
  module's documented impact score — severity 100.0, 8/8 modules, nothing
  hidden."
- `release_pairs_backtest.png` — "The deterministic pairs demo: 119 trades,
  −23.0% vs +112.7% buy-and-hold. Yes, the strategy loses — honest numbers
  are the feature."
- `release_home_768.png` — "Same dashboard at tablet width — the responsive
  defects the browser smoke test caught are now regression-guarded."

## 5. What NOT to claim (hard rules)

- No production-trading, execution, or broker connectivity claims.
- No investment/trading/allocation advice, ever — including in replies.
- No alpha, returns, or performance promises (the demo strategy *loses* —
  cite it as honesty, never as a signal).
- No user/customer/revenue numbers — there are none.
- No "audited", "certified", "institutional-grade", "production-ready".
- No live-data guarantee — adapters are opt-in and fail closed.
- Cite only recorded evidence (2,968 backend tests, 12/12 E2E) as *recorded
  runs*, not as guarantees.

## 6. Hashtag suggestions

`#quantfinance #python #fastapi #nextjs #typescript #playwright #testing
#buildinpublic #softwareengineering #fintech` — pick 3–5; skip any that
imply trading services.

## 7. Comment reply templates

- **"Can it trade live?"** — "No, by design — QuantLab has no broker
  connectivity or order path. It's an educational research platform; the
  interesting part is the deterministic, testable engineering."
- **"Does the pairs strategy work?"** — "The demo deliberately shows a
  losing strategy on deterministic sample data — it demonstrates the
  workflow and honest reporting, not a signal. Nothing in the project is
  investment advice."
- **"Is the data real?"** — "Deterministic hand-written samples in most
  labs, user-supplied CSVs in the engines, and optional adapters that are
  off by default and fail closed. Tests never touch a live provider."
- **"Can I try it?"** — "Yes — clone it, `pip install` + `npm install`, two
  local servers. The LOCAL_DEMO_GUIDE walks it end to end."
- **"Why educational only?"** — "Scope honesty. Production trading needs
  execution, market data contracts, and compliance layers I deliberately
  didn't build — the limitations doc lists all of it."

## Ground rules (unchanged by this doc)

Honest, technical, portfolio-oriented. Not investment advice; not a trading
system; no performance claims; deterministic sample data.
