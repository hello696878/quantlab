# QuantLab — Visual Redesign & Global Markets Globe v1.1

A design-first upgrade to QuantLab's terminal UI. Centerpiece: the **Global Markets
Globe** reimagined as a "mission control" page, on top of a shared design-token system
that keeps every module cohesive.

> **Honesty constraints (enforced in the UI):** every data surface is labelled **Static
> sample / synthetic**. No live data, no real-time claims, no broker/trading, no API keys,
> no "institutional terminal" claim. Cross-links open existing QuantLab labs only.

Open `QuantLab Terminal.html` → **Markets Globe** (and **Dashboard**).

---

## 1. Overall visual direction

Premium quant-research terminal: dark, cinematic, high-contrast. Bloomberg seriousness +
Linear/Vercel polish. Glass panels over a deep navy-black base with a faint grid texture, an
accent **aurora** glow, thin hairline borders, and restrained neon — accent reserved for
data, active states, and focus. Dense but readable; tuned for screenshots. The accent is a
single themeable token (6 themes) so the whole product flexes identity without a redesign.

**Avoided:** generic SaaS dashboard, random neon, low-contrast text, dead whitespace,
Bootstrap defaults, toy globe, cyberpunk overload, unreadable tables.

---

## 2. Color palette (`app/tokens.css`)

**Surfaces** — `--bg-void #05070d` · `--bg-base #080b14` · `--bg-panel #0c1120` · `--bg-elev #11182b`
**Glass** — `--glass rgba(255,255,255,.03)` · `--glass-strong .055` · `--glass-hover .075`
**Borders** — `--line rgba(255,255,255,.07)` · `--line-strong .12` · `--line-faint .04`
**Text ramp** — `--text-hi #e8ecf6` · `--text #b4bccd` · `--text-mut #79839a` · `--text-faint #4f586d`
**Accent (themeable)** — `--accent` (default cyan `oklch(.82 .13 205)`), `--accent-2`, plus derived
`--accent-soft/-softer/-line/-ink` and `rgba(var(--accent-rgb), …)` for glows.
**Semantics (fixed across themes)** — `--pos oklch(.80 .15 162)` · `--warn oklch(.82 .14 80)` · `--neg oklch(.68 .19 18)`
**Globe regions** — Americas `#5b9bff` · Europe `#2bd6a0` · Asia-Pacific `#f0b648` · Global `#34d6e0`

Six accent themes live in `:root[data-accent="…"]` (cyan, blue, emerald, violet, amber, risk-red).
See `THEME_SYSTEM.md` for the full theme treatment.

---

## 3. Typography scale

- **UI:** Manrope (400–800) · **Data / figures / tickers:** JetBrains Mono (tabular nums)
- `--t-2xs 10.5 · xs 11.5 · sm 13 · base 14.5 · md 16 · lg 19 · xl 24 · 2xl 31 · 3xl 42 · 4xl 56`
- `.uplabel` = 10.5px / 0.13em / uppercase / muted — the label workhorse.
- **Hierarchy rule:** page title 19–24 (Manrope 700), section label `.uplabel`, metric value
  22–31 (Mono 700), body 13–14.5. Numbers are always mono + tabular.

## 4. Spacing scale — 4px base
`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64`. Page padding 22–28; card padding 13–18; grid
gaps 12–14. Section rhythm 18.

## 5. Radius / shadow
Radius `--r-xs 6 · sm 9 · md 13 · lg 18 · xl 24 · pill`. Cards use `--r-lg`.
Shadow `--sh-sm/-md/-lg` + `--glow` (accent ring + soft bloom) + `--glow-soft`.

---

## 6. Card system
`.glass` = glass fill + 1px `--line` + 18px radius + backdrop blur. `.sheen` adds a top
hairline highlight. Variants react to `data-cardstyle` (glass / solid / outline). `Panel`
component = titled glass card with optional `accent` glow + a `right` slot. Hover lifts use
`translateY(-2/3px)` + accent border warm.

## 7. Metric card system (`MetricCard`)
**Contrast is non-negotiable** — values are `--text-hi` (#e8ecf6) or `--accent-ink`, never dark
on dark, never low-opacity. Layout: small muted `.uplabel` → large mono value (count-up
animated) → optional delta pill (semantic color) + sub-caption. `accent` variant adds
`--accent-line` border + soft glow. Min height 104; values `whiteSpace: nowrap`,
`clamp(21px,2vw,26px)`.

## 8. Button system
`.btn-primary` (solid accent gradient, `--on-accent` ink, restrained glow) · `.btn-secondary`
(glass + accent-line border, warms on hover) · `.btn-ghost` (text, accent on hover) ·
`RunButton` (primary + loading spinner). All read accent tokens, so they re-theme live.

## 9. Tab system
`.tabbar` + `.tab` / `.tab.active` (accent-soft fill + accent-line ring). Comfortable
6–13px padding, 4px gap. On mobile the bar scrolls horizontally (`overflow-x:auto`), never
wraps cramped.

## 10. Table system
Header row = `.uplabel`. Rows separated by `--line-faint`; hover wash `--glass`. Selected
row = `.row-selected` (accent-soft + 3px accent inset bar). Numbers mono + right-aligned +
tabular. Status via `Badge` pills (pos/neg/warn/accent). Wrap in `overflow-x:auto` with a
sensible `min-width`. No raw-JSON look.

## 11. Chart styling guide
Dark transparent backgrounds; gridlines `rgba(255,255,255,.05)`. **Primary series =
`--accent`**, **secondary/benchmark = `--accent-2`** (dashed) — never all-cyan. Positive
`--pos` / negative `--neg`. Crosshair tooltip in glass with mono values. Heatmap ramp
interpolates `--accent-2-hue → --accent-hue` in oklch (re-themes live). Charts are hand-built
SVG/Canvas (`app/charts.jsx`, `app/globe.jsx`) — no chart lib, no textures.

---

## 12. Global Markets Globe — layout spec (`app/pages-globe.jsx`)

Three-zone "mission control", width-aware via `useContainerMode` (ResizeObserver + window
resize):

| Mode | Trigger | Layout (CSS grid-template-areas) |
|---|---|---|
| **wide** | ≥1120px | `"rail globe dossier"` — 248px / 1fr / 372px |
| **mid** | 720–1119 | `"globe globe" / "rail dossier"` — globe full-width on top |
| **narrow** | <720px | `"globe" / "rail" / "dossier"` — fully stacked, no h-overflow |

- **Left rail:** market search · region filter chips (All/Americas/Europe/APAC/Other) · market
  count · scrollable market list (region dot, flag, code·exchange, lead-index %) · quick-jump
  buttons (US/UK/Japan/HK). Selected row uses `.row-selected`.
- **Center:** the globe canvas + a top overlay (title, v1.1 badge, **auto-rotate toggle**,
  **reset view**) and a bottom **legend** (4 region colors + arc key).
- **Right dossier:** sticky selected-market header + full dossier (§14).
- **Bottom strip:** global market **tape** — Americas / Europe / Asia-Pacific region cards
  (avg %, advancers/decliners) + a selected-market mini-sparkline card.

## 13. Globe interaction spec (`app/globe.jsx`)

Hand-built **canvas 2D** orthographic globe — no WebGL, no textures, no GeoJSON (honest
stylized data-viz, not cartography):

- **Sphere:** radial-gradient ocean with offset shading + accent **atmosphere halo** + rim light.
- **Land:** coarse lat/lon-box **dot-matrix** mask (denser, brighter dots toward the viewer).
- **Graticule:** 30° lat/lon lines, front hemisphere only.
- **Markers:** region-colored, **pulsing** glow + ring; selected marker gets a larger ring +
  city/code label. Far-side markers are hidden (back-face culling via `vz>0`).
- **Arcs:** great-circle (slerp) **capital-flow** lines lifted off the surface with a travelling
  pulse; illustrative connections (US↔UK, US↔JP, CN↔HK, TW↔US, SG↔IN, …).
- **Starfield** background; **drag to rotate** (yaw+pitch, pitch clamped); **auto-rotate**
  toggle; **reset view**; **hover tooltip**; **click marker → select**.
- **Performance:** `requestAnimationFrame` ticker (browser-paused in hidden tabs), roughly 30 fps
  during motion and throttled under reduced motion, DPR-capped to 2, ~6k land-dot
  samples/frame. Region filter dims non-matching markers/arcs and removes them from hit-testing.

## 14. Dossier panel spec

Premium financial-intelligence card. **Sticky header:** flag, country, region dot, currency,
exchange, timezone, **bias pill** (Bullish/Bearish/Neutral), **Static-sample badge**, "Last
updated: Static sample", accent band. Sections:
1. **Market Pulse** — index rows with sparkline + change% (pos/neg colored).
2. **Macro Vitals** — GDP growth / inflation / unemployment / policy rate / debt-GDP stat cards.
3. **FX & Rates** — currency · key pair · policy + a one-line note.
4. **Market Structure** — exchange / hours / settlement / listed / market-cap label + note.
5. **Headlines** — 2–3 **sample** headlines, each with a sentiment pill, clearly labelled sample.
6. **QuantLab Actions** — Backtest index · Open Scanner · View FX Lab · View Rates Lab ·
   Country Dossier (honest cross-links; no fake live data).

## 15. Dashboard / Command Center redesign spec (`app/pages1.jsx`)

Hero metric row (NAV / Return / Sharpe / Max DD — animated, high-contrast) → **Global Markets**
strip (region tape cross-linking to the Globe, static-sample badge) → blended equity chart +
Overfitting-risk gauge → strategy watchlist + activity feed. Consistent 28px padding, 14px
gaps, `auto-fit minmax` grids that reflow without clipping.

---

## 16. Shared component list

`Sidebar` · `TopBar` (+ `ThemeSwitcher`, `ApiStatus`, `Clock`) · `Panel` · `MetricCard` ·
`Badge` · `RunButton` · `StrategySelector` · `ParamSlider` · `AlertCard` · `TradeTable` ·
charts (`EquityChart`, `DrawdownChart`, `Sparkline`, `SweepHeatmap`, `WfBars`, `ScoreGauge`) ·
globe (`DataGlobe`, `Dossier`, `MarketRow`, `MarketTape`, `SampleBadge`) · helper classes
(`.btn-*`, `.tab`, `.badge-accent`, `.row-selected`, `.field-input`, `.report-accent-band`).

## 17. Mobile behavior
Globe page collapses wide → mid → narrow (above). In narrow: globe on top (380px), market
list expands inline (no nested scrollbar), dossier below; no horizontal overflow. Tabs &
tables scroll horizontally. Metric/strip grids are `auto-fit minmax` so they re-wrap. Hit
targets ≥36–44px.

## 18. Accessibility notes
- Text contrast: body/value tokens clear AA on the dark base; never dark-on-dark or
  low-opacity values (enforced in metric cards).
- Accent never the *only* signal — direction also shown via +/- sign, arrows, and word labels
  (Bullish/Bearish), so the 6 accent themes (incl. red Risk mode) stay colorblind-safe.
- Focus rings on inputs/buttons (`--accent` + ring). Keyboard-reachable controls.
- `prefers-reduced-motion`: gate auto-rotate / pulses (see checklist).
- Status semantics (API online, success/warn/danger) are fixed colors, not the accent.

---

## Implementation checklist (for Claude Code → Next.js `frontend/`)

**Tokens & shell**
- [ ] Port `app/tokens.css` `:root` + `:root[data-accent]` blocks into `globals.css` (`@layer base`); map in `tailwind.config.ts` (`colors.accent`, `accent-soft/-line`, `boxShadow.glow`, `borderRadius`, `fontFamily`).
- [ ] Set `data-accent` on `<html>` from a theme provider (cookie/localStorage); add the 6-swatch `ThemeSwitcher` to the top bar.
- [ ] Add the body backdrop (aurora + masked grid) to the app shell.

**Shared components → `src/components/`** (convert inline styles to Tailwind; keep token names)
- [ ] `Panel`, `MetricCard` (enforce `text-hi`/`accent-ink` values — audit for any dark-on-dark), `Badge`, `Button` (primary/secondary/ghost), `Tabs`, `Table` (sticky header, `.row-selected`), `AlertCard`, `SampleBadge`.
- [ ] Charts as `.tsx` (dependency-free SVG): primary `--accent`, secondary `--accent-2`, heatmap hue-lerp.

**Global Markets Globe**
- [ ] Add `globe-data.ts` (markets w/ lat·lon·region·dossier, arcs, land-box mask) — keep the **Static sample** labelling.
- [ ] Port `DataGlobe` canvas component (orthographic projection, dot-matrix land, graticule, atmosphere, pulsing markers, slerp arcs, drag/auto-rotate/reset, hover tooltip). Gate motion on `prefers-reduced-motion`.
- [ ] Build the 3-zone page with `useContainerMode` breakpoints (wide/mid/narrow) via `grid-template-areas`.
- [ ] Dossier panel with the 6 sections + honest QuantLab cross-links (route to existing labs).
- [ ] Bottom region tape from a `regionRollup()` helper.

**Dashboard**
- [ ] Hero metric row + Global-Markets strip (cross-link to Globe) + equity/risk + watchlist/activity.

**Polish & guardrails**
- [ ] Skeleton loaders, friendly error panels, and **"Static sample / synthetic data"** badges on every data surface.
- [ ] Verify no horizontal overflow at 360 / 768 / 1280 / 1600.
- [ ] Confirm contrast (no dark-on-dark values) and keyboard focus on all interactive elements.
- [ ] Do **not** add live data, trading, API keys, or real-time/institutional claims.

---

*Design prototype only — no real APIs, no repository changes.*
