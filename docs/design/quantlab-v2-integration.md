# QuantLab Terminal — Design Prototype

A high-fidelity, **design-only** prototype for the QuantLab quant research dashboard.
Dark quant-terminal aesthetic crossed with a modern AI research lab. Six workspaces +
a live Design Tokens reference, all driven by **seeded mock data** that mirrors your
real FastAPI response shapes. **No network calls. Your repo is untouched.**

Open `QuantLab Terminal.html`.

---

## 1. What's in the prototype

| Page | File | Highlights |
|------|------|-----------|
| **Dashboard** | `app/pages1.jsx` | Portfolio hero metrics, blended equity vs benchmark, Overfitting Risk gauge, strategy watchlist (click a row → backtest), activity feed |
| **Backtest Workspace** | `app/pages1.jsx` | Strategy selector, universe + parameter controls, **Run** with loading skeleton, 8-metric strip, equity + drawdown charts, trade log |
| **Research Tools** | `app/pages2.jsx` | Tool launcher + **Train/Test out-of-sample validation** hero with IS→OOS degradation table and the "OOS collapsed" alert |
| **Strategy Comparison** | `app/pages2.jsx` | Ranking cards, 5-strategy normalized equity overlay, side-by-side metrics table |
| **Parameter Sweep** | `app/pages2.jsx` | Interactive fast×slow **heatmap** (switch metric, click a cell), best-params panel, overfit-spike warning |
| **Walk-Forward** | `app/pages2.jsx` | Aggregate OOS metrics, stitched equity, per-window train-vs-test Sharpe bars, **parameter-stability** diagnostic, overfitting factor breakdown |
| **Design Tokens** | `app/pages3.jsx` | In-app spec: color, type, spacing, radius, shadows, components |

### Signature feature — Overfitting Risk Score
A composite 0–100 diagnostic (`QL.overfittingScore` in `app/mockdata.jsx`) blending
IS→OOS Sharpe decay, parameter instability, sweep dispersion, and OOS drawdown
worsening. Surfaces as a radial gauge on the Dashboard and Walk-Forward pages — the
through-line of the "is this strategy real or overfit?" narrative.

---

## 2. Component structure

```
QuantLab Terminal.html          ← shell: fonts, React/Babel, script order, #root
app/
├─ tokens.css                   ← all design tokens (CSS custom properties) + base + primitives
├─ mockdata.jsx                 ← window.QL: seeded generators matching API schemas
├─ charts.jsx                   ← hand-built SVG charts (no chart lib)
│     EquityChart, DrawdownChart, Sparkline, SweepHeatmap, WfBars, ScoreGauge
├─ components.jsx               ← shared UI
│     Sidebar, TopBar, ApiStatus, Clock, MetricCard, StrategySelector,
│     ParamSlider, AlertCard, TradeTable, Panel, Badge, RunButton, Logo, Icon
├─ tweaks-panel.jsx             ← in-design Tweaks (accent theme, glow, card style, grid)
├─ pages1.jsx                   ← DashboardPage, BacktestPage, MetricsStrip
├─ pages2.jsx                   ← ResearchPage, ComparePage, SweepPage, WalkForwardPage, MultiEquity
└─ pages3.jsx                   ← TokensPage, App (router + shell + tweaks wiring)
```

**Patterns worth keeping**
- **Single source of layout truth:** fixed 224px sidebar + natural document flow (`margin-left: 224px`). This renders and exports/screenshots reliably — a nested `overflow:auto; height:100vh` column does **not**.
- **Charts read CSS variables**, so they restyle instantly when the accent theme changes.
- **`MetricCard` count-up** animates the figure; semantic color (`pos`/`neg`/`warn`) is data-driven.
- **Hover/active states are CSS classes** (`.navbtn`, `.navbtn.active`), never imperative `element.style` mutation — the latter fights React reconciliation.

---

## 3. Design tokens

All defined as CSS custom properties in `app/tokens.css`. Accent theme swaps at runtime via
`<html data-accent="blue|cyan|emerald">` (the Tweaks panel sets this).

### Color
| Token | Value | Use |
|-------|-------|-----|
| `--bg-void` / `--bg-base` | `#05070d` / `#080b14` | App background (deep navy-black) |
| `--bg-panel` / `--bg-elev` | `#0c1120` / `#11182b` | Solid panels / raised |
| `--glass` … `--glass-hover` | `rgba(255,255,255,.03→.075)` | Translucent card fills |
| `--line` / `--line-strong` | `rgba(255,255,255,.07 / .12)` | Hairline borders |
| `--text-hi / text / mut / faint` | `#e8ecf6 / #b4bccd / #79839a / #4f586d` | Text ramp |
| `--blue` (primary) | `oklch(.72 .16 256)` | Electric blue accent |
| `--cyan` | `oklch(.82 .13 205)` | Secondary accent |
| `--emerald` / `--pos` | `oklch(.80 .15 162)` | Gains |
| `--neg` | `oklch(.68 .19 18)` | Losses |
| `--warn` | `oklch(.82 .14 80)` | Warnings / overfit |

Accents live in **oklch** (uniform lightness/chroma) so the three themes feel equally weighted.

### Typography
- **UI:** Manrope (400–800) — `--font-ui`
- **Data / figures / tickers:** JetBrains Mono (400–700) — `--font-mono`, tabular numerals
- Scale: `--t-2xs 10.5` · `xs 11.5` · `sm 13` · `base 14.5` · `md 16` · `lg 19` · `xl 24` · `2xl 31` · `3xl 42` · `4xl 56`
- `.uplabel` = 10.5px, 0.13em tracking, uppercase, muted — the section-label workhorse.

### Spacing — 4px base
`--s-1 4 · s-2 8 · s-3 12 · s-4 16 · s-5 20 · s-6 24 · s-8 32 · s-10 40 · s-12 48 · s-16 64`

### Radius
`--r-xs 6 · sm 9 · md 13 · lg 18 · xl 24 · pill 999`  (cards use `--r-lg`)

### Shadows / elevation
| Token | Value |
|-------|-------|
| `--sh-sm` | `0 1px 2px rgba(0,0,0,.4)` |
| `--sh-md` | `0 4px 16px rgba(0,0,0,.35), 0 1px 2px rgba(0,0,0,.4)` |
| `--sh-lg` | `0 18px 50px -12px rgba(0,0,0,.65), 0 2px 8px rgba(0,0,0,.4)` |
| `--glow` | accent ring + `0 0 28px -4px rgba(accent,.45)` |
| `--glow-soft` | `0 0 24px -8px rgba(accent,.35)` |

Plus the ambient backdrop: a fixed accent **aurora** (`body::before`) over a masked **44px grid** (`body::after`, toggleable via `--grid-display`).

---

## 4. Mock data ↔ your API

`app/mockdata.jsx` deliberately mirrors `backend/app/schemas.py` so swapping in the real API
is a data-source change, not a re-layout. Shapes already match:

- **`PerformanceMetrics`** — `total_return, cagr, sharpe_ratio, sortino_ratio, max_drawdown, volatility, calmar_ratio, win_rate, num_days`
- **`EquityPoint`** — `{ date, strategy, benchmark }`
- **`SmaSweepRow`** — `{ fast_window, slow_window, sharpe_ratio, cagr, total_return, sortino_ratio, calmar_ratio, max_drawdown, volatility, num_trades }`
- **Train/Test** & **Walk-Forward** windows — IS/OOS metrics, degradation deltas, `parameter_stability`

Numbers are calibrated to realistic ranges (portfolio ≈ 14% CAGR / Sharpe 1.5 / −22% DD;
per-strategy Sharpe 1.1–1.6; walk-forward degrades to a still-positive Sharpe 0.78) — strong
but not suspiciously perfect.

---

## 5. Integrating into your Next.js app later

> This prototype is plain React + Babel-in-browser for instant preview. Below is how a
> developer (or Claude Code) would port it into your real `frontend/` (Next.js App Router + Tailwind).

**Step 1 — Tokens → Tailwind.** Port `app/tokens.css` `:root` variables into
`globals.css` under `@layer base`, and map them in `tailwind.config.ts`
(`theme.extend.colors`, `fontFamily`, `borderRadius`, `boxShadow`). Keep the
`data-accent` theme switch — it's just CSS variables.

**Step 2 — Charts.** Move `charts.jsx` into `src/components/charts/` as `.tsx`.
They're dependency-free SVG and already prop-driven; add types from `src/lib/types.ts`.
Replace the `useDrawn`/transition entrance with `framer-motion` if you want richer motion
(the current "snap to final state" exists only to survive the static preview sandbox).

**Step 3 — Components.** Port `components.jsx` into `src/components/` (`Sidebar`,
`TopBar`, `MetricCard`, `StrategySelector`, `ParamSlider`, `AlertCard`, `TradeTable`,
`Panel`, `Badge`, `RunButton`). Convert inline style objects to Tailwind classes (the
token names line up 1:1). Keep hover/active as CSS/Tailwind classes, not JS style mutation.

**Step 4 — Routing.** The prototype's hash router becomes App Router segments:
`/dashboard`, `/backtest`, `/research`, `/compare`, `/sweep`, `/walk-forward`. Lift the
`Sidebar` + `TopBar` into `app/(dashboard)/layout.tsx`. Each page becomes
`app/(dashboard)/<route>/page.tsx`.

**Step 5 — Real data.** Replace `window.QL.*` reads with your existing fetch layer
(server components / route handlers calling FastAPI). Because the mock shapes already match
your Pydantic schemas, components consume real responses unchanged. Wire `RunButton` to your
backtest POST; feed the `loading` state from the request.

**Step 6 — Overfitting score.** Port `overfittingScore()` either client-side (from
existing metrics) or, better, compute it in the backend alongside walk-forward results and
return it as a field.

**What NOT to copy:** the in-browser Babel `<script>` tags, the `useDrawn`/transition
work-arounds, and the Tweaks panel (a design-exploration tool, not a product feature) —
though `data-accent` theming is worth keeping as a user preference.

---

*Prototype only — no real API calls, no changes to your repository.*
