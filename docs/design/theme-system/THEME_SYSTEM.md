# QuantLab — Theme System

A complete accent-theme system for the QuantLab terminal. **One token re-skins the
entire product**, not just the sidebar. Design-only prototype — no APIs, repo untouched.

Open `QuantLab Terminal.html` → **Theme System** in the sidebar (or use the 6 swatches in
the top bar on any page).

---

## 1. The problem (before) → the fix (after)

**Before.** The accent setting only reached the **sidebar active state**. Buttons, charts,
metrics, badges, tables, and headers were all hardcoded to one blue/cyan, so changing the
"theme" barely changed anything — the product had no single visual identity to flex.

**After.** Every accent-tinted surface reads from **one set of accent tokens**. Flipping
`data-accent` on `<html>` re-skins all of them at once:

| Surface | Token it reads |
|---|---|
| Sidebar active state | `rgba(var(--accent-rgb), .12)` + `inset 2px 0 0 var(--accent)` |
| Primary button | `var(--accent)` → `var(--accent-2)` gradient, `var(--on-accent)` text |
| Secondary button | `var(--accent-line)` border → `var(--accent)` on hover |
| Input focus ring | `var(--accent)` border + `rgba(var(--accent-rgb), .22)` ring |
| Active tab | `var(--accent-soft)` bg + `var(--accent-line)` ring |
| Chart primary line | `var(--accent)` |
| Chart secondary line | `var(--accent-2)` (dashed, subordinate) |
| Metric card highlight | `var(--accent-line)` border + `rgba(var(--accent-rgb), …)` glow |
| Badge / chip | `var(--accent-soft)` + `var(--accent-line)` |
| Table selected row | `var(--accent-soft)` + `inset 3px 0 0 var(--accent)` |
| Heatmap ramp | interpolates `--accent-2-hue` → `--accent-hue` in oklch |
| Glow effects | `rgba(var(--accent-rgb), …)` + `var(--glow)` |
| Report header band | `var(--accent)` → `var(--accent-2)` gradient |
| API online indicator | **stays green** — it's a status semantic, not an accent |
| Risk / warning cards | **stay amber / red** — semantic, not accent |

The **Theme System** page renders all of these as a live specimen board plus a side-by-side
Before/After so you can see the reach at a glance.

---

## 2. The six accents

All tuned to the same perceptual lightness (~0.7–0.82 L) and chroma so the UI keeps its
weight and contrast no matter which is active — it never turns into a rainbow.

| Theme | `--accent` (oklch) | Intended use |
|---|---|---|
| **Cyan** (default) | `0.82 0.13 205` | Cool analytics |
| **Blue** | `0.72 0.16 256` | Classic institutional |
| **Emerald** | `0.80 0.15 162` | Performance / growth |
| **Violet** | `0.69 0.17 292` | Research / quant lab |
| **Amber** | `0.82 0.13 78` | Warm reporting decks |
| **Risk (red)** | `0.64 0.20 22` | Stress / risk mode — also deepens `--neg` so up/down stays legible |

---

## 3. Token system (CSS variables)

Defined in `app/tokens.css`. **Themes override only the primitives**; the derived tokens
cascade automatically, so adding a new accent is ~4 lines.

### Per-theme primitives (set under `:root[data-accent="…"]`)
```css
--accent        /* the accent color                         */
--accent-2      /* harmonized partner hue (secondary line)   */
--accent-rgb    /* "r, g, b" for rgba() glows + soft fills    */
--accent-2-rgb
--accent-hue    /* oklch hue number — drives the heatmap ramp */
--accent-2-hue
```

### Derived accent tokens (declared once in `:root`, auto-cascade)
```css
--accent-soft:   color-mix(in oklch, var(--accent) 15%, transparent);
--accent-softer: color-mix(in oklch, var(--accent) 8%,  transparent);
--accent-line:   color-mix(in oklch, var(--accent) 40%, transparent);
--accent-ink:    color-mix(in oklch, var(--accent) 88%, white);
--on-accent:     #05070d;  /* text on a solid accent fill */
--glow:          0 0 0 1px color-mix(in oklch, var(--accent) 55%, transparent),
                 0 0 28px -4px rgba(var(--accent-rgb), 0.45);
```

### Background colors
```css
--bg-void: #05070d;  --bg-base: #080b14;  --bg-panel: #0c1120;  --bg-elev: #11182b;
```

### Card / glass colors
```css
--glass: rgba(255,255,255,.030);  --glass-strong: rgba(255,255,255,.055);
--glass-hover: rgba(255,255,255,.075);
/* .glass = glass bg + 1px var(--line) + 18px radius + backdrop blur */
```

### Border colors
```css
--line: rgba(255,255,255,.07);  --line-strong: rgba(255,255,255,.12);  --line-faint: rgba(255,255,255,.04);
```

### Chart colors
```
primary   = var(--accent)
secondary = var(--accent-2)        /* benchmark, dashed */
heatmap    = oklch(L, C, lerp(--accent-2-hue → --accent-hue))
comparison = a fixed 5-color categorical palette (accent + cyan + emerald + amber + violet)
```

### Semantic colors (intentionally **stable** across themes)
```css
--pos:  oklch(.80 .15 162);  /* gains — green   */
--warn: oklch(.82 .14 80);   /* warnings — amber */
--neg:  oklch(.68 .19 18);   /* losses — red    */  /* deepens slightly in Risk mode */
```
Keeping up/down + success/warning/danger fixed is the institutional-correct choice and is
why six accents never make the app look childish.

---

## 4. Component breakdown (what changed)

```
app/tokens.css        6 accent themes + derived accent tokens + themed helper classes
                      (.btn-primary/.btn-secondary/.tab/.badge-accent/.row-selected/.swatch …)
app/components.jsx    THEMES catalog · ThemeSwitcher (6 swatches) · applyAccent()
                      TopBar now renders the live switcher
app/charts.jsx        SweepHeatmap ramp follows --accent-hue; best-cell + WF test bars → --accent-2;
                      EquityChart benchmark line → --accent-2
app/pages-theme.jsx   ThemeSystemPage — picker, Before/After mini-apps, 14-tile specimen board
app/pages3.jsx        App wires setTheme(); re-render key `page + ":" + accent` so chart
                      canvases re-read CSS vars on swap; Tweaks panel lists all 6 accents
```

**One implementation detail worth keeping:** charts that read CSS variables in JS
(`getComputedStyle`) won't notice a class/attribute swap on their own. Two robust options —
this prototype uses (a):
- **(a)** apply `data-accent` **synchronously** in the click handler, and key the page subtree
  on the accent so it re-mounts and re-reads; or
- **(b)** drive the chart hue from a React state/context prop instead of reading the DOM.

---

## 5. Integrating into your Next.js app (for Claude Code)

> Goal: make the existing accent setting affect the whole product, the way this prototype does.

**Step 1 — Adopt the token layer.** Copy the accent primitives + derived tokens from
`app/tokens.css` into your `globals.css` under `@layer base`. Keep the
`:root[data-accent="…"]` blocks. If you use Tailwind, expose them in `tailwind.config.ts`:
```ts
colors: {
  accent: 'var(--accent)', 'accent-2': 'var(--accent-2)',
  'accent-soft': 'var(--accent-soft)', 'accent-line': 'var(--accent-line)',
}
boxShadow: { glow: 'var(--glow)' }
```
Then components use `bg-accent`, `border-accent-line`, `text-accent`, `shadow-glow`, or
`bg-[rgba(var(--accent-rgb),0.12)]`.

**Step 2 — Set the attribute high up.** Write `data-accent` onto `<html>` in your root
layout from a theme provider / user preference (cookie or `localStorage`). One line; every
descendant inherits it.

**Step 3 — Replace hardcoded accent values.** Search the codebase for the literal blue/cyan
hex(es) currently used for buttons, focus rings, active tabs, chart series, badges, and
selected rows, and swap each for the matching token above. This is the bulk of the work and
is what makes the accent actually "reach" the whole UI.

**Step 4 — Theme the charts.** Whatever chart lib you use (Recharts/visx/etc.), feed series
colors from the tokens, e.g. `stroke="var(--accent)"` for the primary series and
`var(--accent-2)` for the benchmark. For a heatmap, interpolate the cell hue between
`--accent-2-hue` and `--accent-hue` (see `SweepHeatmap` in `app/charts.jsx`). If your chart
reads colors in JS, re-read them when `data-accent` changes (React state/key or a
`MutationObserver` on `<html>`).

**Step 5 — Switcher UI.** Port `ThemeSwitcher` (6 swatches) into your top bar and persist the
choice. The `THEMES` array in `app/components.jsx` is drop-in.

**Keep semantics out of the accent.** Leave success/warning/danger and the API status
indicator on their own fixed tokens — don't route them through `--accent`.

---

*Prototype only — no real API calls, no changes to your repository.*
