# Visual Redesign — Implementation Notes (Phase 20.1)

How the **Claude Design** redesign (see `VISUAL_REDESIGN.md`, `THEME_SYSTEM.md`,
`INTEGRATION.md`, and `QuantLab Terminal.html`) was implemented into the real
QuantLab Next.js app. This was a **UI/UX pass only** — no finance/backtest/
options/AFML/scanner logic was changed, no live data, no API keys, no new npm
dependencies.

## What was already in place (no change needed)

The repo's design token layer and shared components were already derived from the
same prototype, so most of the design system existed before this pass:

- `globals.css` already carries the full token set (`--bg-*`, `--glass*`,
  `--line*`, the `--text-hi/text/mut/faint` ramp, the six `:root[data-accent]`
  themes, derived accent tokens, `--glow`, the aurora + masked-grid backdrop) and
  the helper classes (`.card`, `.glass`, `.sheen`, `.uplabel`, `.section-title`,
  `.navbtn`, `.ql-segmented`, `.rise`, `.neon-divider`).
- `tailwind.config.ts` maps the inverted slate ramp, accent (`blue-*`) reach,
  radius, and shadows.
- `MetricCard`, `Sidebar`, `TopBar`, and the lab panels already used these tokens.

Because the token system was already present, this pass did **not** re-port
`tokens.css` or add a `ThemeSwitcher` (the accent system already cascades; the
six themes already exist). Adding a top-bar theme switcher remains optional
future polish.

## What this pass implemented

### Global Markets Globe v1.1 (centerpiece)
- `components/globe/DataGlobe.tsx` — **new canvas 2D** mission-control globe
  (orthographic projection, dot-matrix landmass mask, atmosphere halo,
  starfield, 30° graticule, region-colored pulsing markers with back-face
  culling, great-circle "capital-flow" arcs with a travelling pulse,
  drag/auto-rotate/reset, hover tooltip). No WebGL, no Three.js, no textures, no
  GeoJSON. `prefers-reduced-motion` gates animation; a missing 2D context shows a
  graceful fallback (the market list stays usable).
- `components/GlobeLabPanel.tsx` — **rebuilt** as a width-aware three-zone layout
  (wide ≥1120 / mid 720–1119 / narrow <720 via a container `ResizeObserver`):
  left rail (search · region filter · market list · quick-jump), center globe
  with overlay controls (spin/reset) + legend, right dossier, bottom region tape.
  The market list contains only matching rows, filtered-out markers are not
  clickable, and a selection is cleared if a new filter excludes it.
- `components/globe/MarketDossier.tsx` — **redesigned**: sticky header with a
  region dot, **bias pill**, "Static demo data" badge, and "Last updated: Static
  sample"; sections renamed to Market Pulse / Macro Vitals / FX & Rates / Market
  Structure / Sample Headlines / QuantLab Actions.
- `lib/globe/markets.ts` — added design **region colors** (Americas `#5b9bff`,
  Europe `#2bd6a0`, APAC `#f0b648`), **`MARKET_ARCS`**, and `marketBias` /
  `regionRollup` helpers. The 15 markets and their values are unchanged static
  sample data.
- The old `components/globe/Globe.tsx` (SVG v1) was removed (only the panel
  imported it).

### Dashboard
- Globe card badge → **"Static data v1.1"**.
- New **Global Markets** region-tape strip (static-sample badge; each region
  cross-links to the globe).

### Metric-card contrast (mandatory, global)
- `MetricCard` already drove values from explicit CSS tokens (`--text-hi`,
  accent/emerald/amber/red) — it stays the source of truth for readable values.
- Fixed dark-on-dark `text-slate-100/200` text in the inverted ramp (where
  100/200 are dark surfaces, not text): the EventLab metric value, AFML / FX /
  Credit / Scanner / Rates education emphasis labels, SaveReport headings, and
  two `hover:text-slate-200` states → bright `text-slate-900` (#e8ecf6).

## Honesty guardrails (enforced in UI + copy)
Every globe surface is labelled **static / sample / synthetic**: a page-header
"Static data v1.1" badge + disclaimer, a globe overlay "Synthetic data-viz"
chip, dossier "Static demo data" + "Last updated: Static sample", and per-section
"planned" notes (live FRED macro, delayed index/FX quotes, news/sentiment,
GeoJSON borders). Index levels/FX are the literal text "Sample"; arcs and the
bias pill are decorative/illustrative. No "live", "real-time", "current prices",
"live news", or "institutional terminal" claims. Not investment advice.

## Verification
- `cd frontend && npx tsc --noEmit` → clean (exit 0).
- No backend files touched; the backend test suite is unaffected.
- Per instructions, **no** `npm run build` / `npm run dev` / `next build` /
  `next dev` was run — the user builds locally.
